import logging, time, io, re, uuid, mimetypes
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from django.core.files.base import File
from django.db import transaction
from django.core.exceptions import ValidationError

from .models import (
    JobApplication, AIProcessingResult, Recruitment
)

logger = logging.getLogger(__name__)

# ---- helpers d’import optionnel (fallbacks gracieux)
try:
    import pdfplumber  # extraction plus clean
except Exception:
    pdfplumber = None

try:
    import PyPDF2  # fallback PDF
except Exception:
    PyPDF2 = None

try:
    import docx  # python-docx
except Exception:
    docx = None


@dataclass
class ScoreWeights:
    skills: float = 0.5
    experience: float = 0.25
    education: float = 0.15
    cover_letter: float = 0.10

DEFAULT_WEIGHTS = ScoreWeights()


class AIRecruitmentService:
    """
    Service de traitement IA (heuristique + branchable OCR/NLP/LLM).
    - Extraction texte (PDF/DOCX/TXT)
    - Analyse CV (compétences, expériences, formations, langues)
    - Analyse lettre (motivation simple)
    - Scoring vs exigences Recruitment.requirements
    - Mise à jour AIProcessingResult + JobApplication
    """

    def __init__(self):
        self.ocr_engine = None   # ex: Tesseract, Vision API (si besoin images)
        self.nlp_engine = None   # ex: spaCy (facultatif)
        self.llm_service = None  # ex: OpenAI/Claude (facultatif)

    # --------- API principale
    def process_application(self, job_application: JobApplication) -> AIProcessingResult:
        start = time.perf_counter()

        self._assert_tenant_consistency(job_application)

        with transaction.atomic():
            ai_result = AIProcessingResult.objects.create(
                job_application=job_application,
                status='PROCESSING',
                tenant_id=job_application.tenant_id
            )

            try:
                # 1) Extraction texte
                cv_text = self._extract_text(job_application.cv)
                cl_text = self._extract_text(job_application.cover_letter) if job_application.cover_letter else ""

                # 2) Analyse CV / Lettre
                extracted = self._analyze_cv(cv_text)
                cl_analysis = self._analyze_cover_letter(cl_text)

                # 3) Scoring vs exigences
                req = job_application.recruitment.requirements or {}
                weights = self._weights_from_recruitment(job_application.recruitment)
                match = self._calculate_match_score(extracted, cl_analysis, req, weights=weights)

                # 4) Remplir AIProcessingResult
                ai_result.extracted_skills = extracted.get('skills', [])
                ai_result.extracted_experience = extracted.get('experience', [])
                ai_result.extracted_education = extracted.get('education', [])
                ai_result.extracted_languages = extracted.get('languages', [])

                ai_result.skills_match_score = match['skills_score']
                ai_result.experience_match_score = match['experience_score']
                ai_result.education_match_score = match['education_score']
                ai_result.overall_match_score = match['overall_score']

                ai_result.missing_skills = match['missing_skills']
                ai_result.strong_skills = match['strong_skills']
                ai_result.experience_gaps = match['experience_gaps']
                ai_result.red_flags = match['red_flags']

                ai_result.ai_model_version = "heuristic-v1"
                ai_result.processing_time = round(time.perf_counter() - start, 3)
                ai_result.status = 'COMPLETED'
                ai_result.save()

                # 5) Mise à jour JobApplication
                job_application.ai_score = ai_result.overall_match_score
                job_application.ai_feedback = {
                    "missing_skills": ai_result.missing_skills,
                    "strong_skills": ai_result.strong_skills,
                    "experience_gaps": ai_result.experience_gaps,
                }

                threshold = job_application.recruitment.minimum_ai_score or 0
                if (job_application.recruitment.ai_scoring_enabled
                        and job_application.ai_score is not None
                        and job_application.ai_score >= threshold):
                    job_application.status = 'AI_SCREENED'
                elif job_application.recruitment.ai_scoring_enabled:
                    job_application.status = 'AI_REJECTED'
                # sinon on laisse le statut courant

                job_application.save()

                logger.info(
                    "Candidature %s traitée: score=%.2f (thr=%.2f)",
                    job_application.id, ai_result.overall_match_score, float(threshold)
                )
                return ai_result

            except Exception as e:
                logger.exception("Erreur traitement IA candidature %s", job_application.id)
                ai_result.status = 'FAILED'
                ai_result.error_message = str(e)
                ai_result.processing_time = round(time.perf_counter() - start, 3)
                ai_result.save()
                raise

    # --------- Extraction texte
    def _extract_text(self, field_file: Optional[File]) -> str:
        if not field_file:
            return ""

        # Toujours ouvrir via storage (S3/MinIO compatible)
        field_file.open('rb')
        try:
            data = field_file.read()
        finally:
            field_file.close()

        if not data:
            return ""

        # Détecter type (par extension ou mime)
        name = getattr(field_file, 'name', '') or 'file'
        mime, _ = mimetypes.guess_type(name)

        # PDF
        if (mime == 'application/pdf') or name.lower().endswith('.pdf'):
            text = self._extract_text_from_pdf_bytes(data)
            if text:
                return text

        # DOCX
        if name.lower().endswith('.docx') and docx:
            try:
                buf = io.BytesIO(data)
                document = docx.Document(buf)
                return "\n".join(p.text for p in document.paragraphs)
            except Exception:
                pass

        # TXT / fallback
        try:
            return data.decode('utf-8', errors='ignore')
        except Exception:
            return ""

    def _extract_text_from_pdf_bytes(self, data: bytes) -> str:
        # pdfplumber → PyPDF2 → fallback
        if pdfplumber:
            try:
                text = []
                with pdfplumber.open(io.BytesIO(data)) as pdf:
                    for page in pdf.pages:
                        text.append(page.extract_text() or "")
                return "\n".join(text).strip()
            except Exception:
                pass

        if PyPDF2:
            try:
                reader = PyPDF2.PdfReader(io.BytesIO(data))
                parts = []
                for page in reader.pages:
                    parts.append(page.extract_text() or "")
                return "\n".join(parts).strip()
            except Exception:
                pass

        return ""

    # --------- Analyse heuristique CV
    def _analyze_cv(self, cv_text: str) -> Dict:
        text = self._normalize(cv_text)

        # très simple détection heuristique
        skills = self._extract_skills(text)
        experience_blocks = self._extract_experience_blocks(text)
        education_blocks = self._extract_education(text)
        languages = self._extract_languages(text)

        years_exp = self._estimate_years_experience(text)

        return {
            "skills": skills,
            "experience": experience_blocks,
            "education": education_blocks,
            "languages": languages,
            "years_experience": years_exp,
        }

    def _analyze_cover_letter(self, cover_text: str) -> Dict:
        text = self._normalize(cover_text)
        if not text:
            return {"motivation_score": 0.0, "length": 0}

        length = len(text.split())
        # heuristique bête : > 120 mots = motivé ; présence de mots-clés
        keywords = ["motivé", "intéressé", "aligné", "valeur", "apprendre", "contribuer"]
        k_bonus = sum(1 for k in keywords if k in text)
        motivation = min(1.0, (length / 200.0) + (0.1 * k_bonus))  # 0..1
        return {"motivation_score": round(100 * motivation, 2), "length": length}

    # --------- Scoring
    def _weights_from_recruitment(self, recruitment: Recruitment) -> ScoreWeights:
        # Si tu veux lire des poids depuis Recruitment.ai_scoring_criteria:
        cfg = recruitment.ai_scoring_criteria or {}
        return ScoreWeights(
            skills=float(cfg.get("w_skills", DEFAULT_WEIGHTS.skills)),
            experience=float(cfg.get("w_experience", DEFAULT_WEIGHTS.experience)),
            education=float(cfg.get("w_education", DEFAULT_WEIGHTS.education)),
            cover_letter=float(cfg.get("w_cover_letter", DEFAULT_WEIGHTS.cover_letter)),
        )

    def _calculate_match_score(
        self,
        candidate_data: Dict,
        cover_letter_analysis: Dict,
        requirements: Dict,
        *,
        weights: ScoreWeights = DEFAULT_WEIGHTS
    ) -> Dict:
        # exigences attendues
        req_skills: List[str] = self._normalize_list(requirements.get("skills", []))
        req_min_years: float = float(requirements.get("min_years_experience", 0))
        req_education_levels: List[str] = self._normalize_list(requirements.get("education_levels", []))

        cand_skills = self._normalize_list(candidate_data.get("skills", []))
        cand_years = float(candidate_data.get("years_experience", 0))
        cand_education = self._normalize_list(candidate_data.get("education", []))

        # Skills score
        overlap = [s for s in cand_skills if s in req_skills]
        missing = [s for s in req_skills if s not in cand_skills]
        strong = overlap[:]
        skills_score = 100.0 * (len(overlap) / len(req_skills)) if req_skills else (100.0 if cand_skills else 0.0)

        # Experience score
        if req_min_years <= 0:
            experience_score = 100.0
            gaps = []
        else:
            ratio = min(1.0, cand_years / req_min_years) if req_min_years else 1.0
            experience_score = round(100.0 * ratio, 2)
            gaps = [] if cand_years >= req_min_years else [f"-{req_min_years - cand_years:.1f} an(s)"]

        # Education score (simple : présence d’un niveau requis → 100)
        edu_hit = any(e in cand_education for e in req_education_levels) if req_education_levels else True
        education_score = 100.0 if edu_hit else 0.0

        # Cover letter
        cover_score = float(cover_letter_analysis.get("motivation_score", 0.0))

        # Red flags : incohérences simples
        red_flags = []
        if cand_years < 0:
            red_flags.append("years_experience_negative")
        if skills_score == 0 and req_skills:
            red_flags.append("no_required_skills")

        overall = (
            skills_score * weights.skills +
            experience_score * weights.experience +
            education_score * weights.education +
            cover_score * weights.cover_letter
        )
        overall = round(overall, 2)

        return {
            "skills_score": round(skills_score, 2),
            "experience_score": round(experience_score, 2),
            "education_score": round(education_score, 2),
            "overall_score": overall,
            "missing_skills": missing,
            "strong_skills": strong,
            "experience_gaps": gaps,
            "red_flags": red_flags,
        }

    # --------- utilitaires d’analyse
    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").lower()).strip()

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"[a-zA-Zàâçéèêëîïôûùüÿñæœ0-9\+\.#\-]+", text)

    def _normalize_list(self, items) -> List[str]:
        if not items:
            return []
        if isinstance(items, str):
            items = [items]
        return [self._normalize(x) for x in items if str(x).strip()]

    def _extract_skills(self, text: str) -> List[str]:
        # heuristique : récupère tokens “tech” fréquents + mots en majuscules/avec +/#
        tokens = set(self._tokenize(text))
        probable = [t for t in tokens if len(t) >= 2 and any(c.isalpha() for c in t)]
        # filtre rudimentaire (garde mots techniques probables)
        keywords = [t for t in probable if re.search(r"[+#\.]|sql|api|http|js|java|python|excel|sap|django|react|node|azure|aws|linux|erp|compta|gestion|logistique", t)]
        # dédoublonne
        return sorted(set(keywords))[:200]

    def _extract_experience_blocks(self, text: str) -> List[Dict]:
        # Placeholder: retourne des “entrées” trouvées par années
        years = re.findall(r"(20\d{2}|19\d{2})", text)
        return [{"year": y} for y in years[:20]]

    def _extract_education(self, text: str) -> List[str]:
        patterns = ["bac\\+\\d", "master", "licence", "bachelor", "doctorat", "phd", "dut", "bts"]
        hits = []
        for p in patterns:
            if re.search(p, text):
                hits.append(p)
        return hits

    def _extract_languages(self, text: str) -> List[str]:
        langs = []
        for k in ["français", "francais", "anglais", "english", "espagnol", "spanish", "allemand", "german", "arabe"]:
            if k in text:
                langs.append(k)
        return sorted(set(langs))

    def _estimate_years_experience(self, text: str) -> float:
        # heuristique simple : “X ans”, “X years”
        m = re.findall(r"(\d{1,2})\s*(ans|years)", text)
        if not m:
            return 0.0
        return max(float(x[0]) for x in m)

    # --------- validations
    def _assert_tenant_consistency(self, job_application: JobApplication):
        rec = job_application.recruitment
        if job_application.tenant_id != rec.tenant_id:
            raise ValidationError("Incohérence tenant entre la candidature et le recrutement.")
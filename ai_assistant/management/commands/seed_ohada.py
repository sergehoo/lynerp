"""
Charge le référentiel OHADA dans la base.

La table ``OHADAArticle`` est globale (pas multi-tenant) : un seul appel
suffit pour tout le projet.

Usage :
    python manage.py seed_ohada
    python manage.py seed_ohada --reset    # purge avant rechargement
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from ai_assistant.models import OHADAArticle
from ai_assistant.ohada.knowledge import OHADA_KNOWLEDGE


class Command(BaseCommand):
    help = "Charge le référentiel OHADA (Actes uniformes, articles pivots)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Supprime toutes les entrées existantes avant rechargement.",
        )

    def handle(self, *args, **opts):
        if opts.get("reset"):
            count = OHADAArticle.objects.all().count()
            OHADAArticle.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Reset : {count} entrées supprimées."))

        created = 0
        updated = 0
        for spec in OHADA_KNOWLEDGE:
            obj, was_created = OHADAArticle.objects.update_or_create(
                reference=spec["reference"],
                defaults={
                    "acte": spec["acte"],
                    "livre": spec.get("livre", ""),
                    "titre": spec.get("titre", ""),
                    "chapitre": spec.get("chapitre", ""),
                    "section": spec.get("section", ""),
                    "article_number": spec.get("article_number", ""),
                    "title": spec["title"],
                    "summary": spec["summary"],
                    "keywords": spec.get("keywords", []),
                    "related_modules": spec.get("related_modules", []),
                    "related_references": spec.get("related_references", []),
                    "version": spec.get("version", "révisé"),
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        total = OHADAArticle.objects.filter(is_active=True).count()
        self.stdout.write(self.style.SUCCESS(
            f"OHADA seed OK — {created} créés, {updated} mis à jour. "
            f"Total actif : {total} articles."
        ))

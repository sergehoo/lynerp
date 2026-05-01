function lyneAIChat() {
    return {
        // ----- état -----
        conversations: [],
        pendingActions: [],
        currentId: null,
        currentTitle: '',
        currentModule: '{{ module|default:"general" }}',
        messages: [],
        input: '',
        streaming: false,
        streamBuffer: '',
        online: true,
        modelLabel: '',
        // ----- recherche web automatique (décidée par le LLM) -----
        // webStatus : '' | 'searching' | 'done'
        webStatus: '',
        webStatusQuery: '',
        webSourcesPreview: [],
        quickActions: [
            { label: 'Résumer cette conversation', text: 'Fais-moi un résumé de notre conversation jusqu’ici.' },
            { label: 'Analyser les recrutements', text: 'Analyse les recrutements ouverts et propose des priorités.' },
            { label: 'Détection d’anomalies finance', text: 'Détecte les anomalies dans les écritures du dernier mois.' },
            { label: 'Aide à la rédaction', text: 'Aide-moi à rédiger un courrier professionnel court.' },
            { label: 'Taux fiscaux pays X', text: 'Donne-moi les taux IRPP / TVA en vigueur en Côte d’Ivoire en 2026.' },
            { label: 'Jurisprudence OHADA', text: 'Cite la jurisprudence CCJA récente sur la responsabilité du gérant de SARL.' },
        ],

        async init() {
            await this.loadConversations();
            await this.loadPendingActions();
            window.addEventListener('online', () => this.online = true);
            window.addEventListener('offline', () => this.online = false);
        },

        // ----- API helpers -----
        async api(method, url, body) {
            const res = await fetch(url, {
                method,
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrf(),
                },
                body: body ? JSON.stringify(body) : null,
            });
            if (!res.ok) {
                const t = await res.text();
                throw new Error(t || ('HTTP ' + res.status));
            }
            return res.json();
        },

        csrf() {
            const m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
            return m ? decodeURIComponent(m[1]) : '';
        },

        // ----- conversations -----
        async loadConversations() {
            try {
                const data = await this.api('GET', '/api/ai/conversations/');
                this.conversations = data.results || data;
                if (this.conversations.length && !this.currentId) {
                    await this.selectConversation(this.conversations[0].id);
                }
            } catch (e) {
                console.error('loadConversations', e);
            }
        },

        async loadPendingActions() {
            try {
                const data = await this.api('GET', '/api/ai/actions/?status=PROPOSED');
                this.pendingActions = (data.results || data).filter(a => a.status === 'PROPOSED');
            } catch (e) { /* silencieux */ }
        },

        async newConversation() {
            try {
                const conv = await this.api('POST', '/api/ai/conversations/', {
                    module: this.currentModule || 'general',
                });
                this.conversations.unshift(conv);
                await this.selectConversation(conv.id);
                this.$refs.input?.focus();
            } catch (e) {
                console.error(e);
            }
        },

        async selectConversation(id) {
            this.currentId = id;
            try {
                const conv = await this.api('GET', `/api/ai/conversations/${id}/`);
                this.currentTitle = conv.title || '';
                this.currentModule = conv.module;
                this.messages = (conv.messages || [])
                    .filter(m => m.role !== 'system')
                    .map(m => {
                        // Réhydrate les sources web stockées en metadata
                        // pour l'affichage du bloc « Sources web ».
                        const meta = m.metadata || {};
                        const srcs = Array.isArray(meta.web_sources) ? meta.web_sources : [];
                        return Object.assign({}, m, { sources: srcs });
                    });
                this.scrollBottom();
            } catch (e) {
                console.error(e);
            }
        },

        // ----- envoi message -----
        async send() {
            const content = this.input.trim();
            if (!content || this.streaming) return;
            if (!this.currentId) {
                await this.newConversation();
            }
            this.input = '';
            this.autoResize(this.$refs.input);

            // optimistic UI
            this.messages.push({
                _tmpId: 'tmp-' + Date.now(),
                role: 'user',
                content,
                created_at: new Date().toISOString(),
            });
            this.scrollBottom();

            this.streaming = true;
            this.streamBuffer = '';
            this.webStatus = '';
            this.webStatusQuery = '';
            this.webSourcesPreview = [];

            try {
                await this.streamResponse(content);
            } catch (e) {
                console.error(e);
                this.messages.push({
                    _tmpId: 'err-' + Date.now(),
                    role: 'assistant',
                    content: '⚠️ ' + (e.message || 'Erreur réseau.'),
                    created_at: new Date().toISOString(),
                });
            } finally {
                this.streaming = false;
                this.streamBuffer = '';
                this.webStatus = '';
                this.webStatusQuery = '';
                this.webSourcesPreview = [];
                await this.loadPendingActions();
                this.scrollBottom();
            }
        },

        async streamResponse(content) {
            const url = `/api/ai/conversations/${this.currentId}/messages/`;
            const res = await fetch(url, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'text/event-stream',
                    'X-CSRFToken': this.csrf(),
                },
                body: JSON.stringify({ content, stream: true }),
            });
            if (!res.ok || !res.body) {
                throw new Error('Erreur ' + res.status);
            }
            const reader = res.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let buf = '';
            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                buf += decoder.decode(value, { stream: true });
                let idx;
                while ((idx = buf.indexOf('\n\n')) !== -1) {
                    const block = buf.slice(0, idx).trim();
                    buf = buf.slice(idx + 2);
                    if (!block.startsWith('data:')) continue;
                    const json = block.slice(5).trim();
                    try {
                        const evt = JSON.parse(json);
                        if (evt.type === 'chunk') {
                            this.streamBuffer += evt.delta;
                            this.scrollBottom();
                        } else if (evt.type === 'web_searching') {
                            // Le router LLM a décidé qu'une recherche web était nécessaire.
                            this.webStatus = 'searching';
                            this.webStatusQuery = evt.query || '';
                            this.scrollBottom();
                        } else if (evt.type === 'web_done') {
                            // Recherche terminée : on conserve les sources pour les attacher
                            // au message final, et on bascule l'indicateur en mode "done".
                            this.webStatus = 'done';
                            this.webSourcesPreview = evt.sources || [];
                            this.scrollBottom();
                        } else if (evt.type === 'done') {
                            this.modelLabel = evt.model || '';
                            this.messages.push({
                                id: evt.message_id,
                                role: 'assistant',
                                content: evt.content,
                                // Sources web automatiques (si recherche déclenchée par le LLM).
                                sources: evt.sources || this.webSourcesPreview || [],
                                created_at: new Date().toISOString(),
                            });
                            this.streamBuffer = '';
                            // Refresh title from server
                            await this.loadConversations();
                        } else if (evt.type === 'error') {
                            throw new Error(evt.message || 'Erreur IA');
                        }
                    } catch (err) {
                        console.warn('parse SSE', err, json);
                    }
                }
            }
        },

        // ----- helpers -----
        autoResize(el) {
            if (!el) return;
            el.style.height = 'auto';
            el.style.height = Math.min(el.scrollHeight, 200) + 'px';
        },

        scrollBottom() {
            this.$nextTick(() => {
                const el = document.getElementById('messageScroll');
                if (el) el.scrollTop = el.scrollHeight;
            });
        },

        formatDate(s) {
            if (!s) return '';
            try {
                const d = new Date(s);
                return d.toLocaleString('fr-FR', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' });
            } catch { return ''; }
        },

        renderMarkdown(text) {
            if (!text) return '';
            // Markdown minimaliste : headings, bold, italic, code, links, listes, retours.
            let html = String(text)
                .replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
                .replace(/```([\s\S]*?)```/g, (_, c) => '<pre><code>' + c + '</code></pre>')
                .replace(/`([^`]+)`/g, '<code>$1</code>')
                .replace(/^### (.*)$/gm, '<h3>$1</h3>')
                .replace(/^## (.*)$/gm, '<h2>$1</h2>')
                .replace(/^# (.*)$/gm, '<h1>$1</h1>')
                .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
                .replace(/(^|[^*])\*([^*]+)\*/g, '$1<em>$2</em>')
                .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
                .replace(/^\s*-\s+(.*)$/gm, '<li>$1</li>')
                .replace(/(?:<li>.*<\/li>\s*)+/g, m => '<ul>' + m + '</ul>')
                .replace(/\n{2,}/g, '</p><p>')
                .replace(/\n/g, '<br>');
            return '<p>' + html + '</p>';
        },
    };
}

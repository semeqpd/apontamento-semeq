/**
 * Password Toggle Component - Reutilizável em todo o projeto
 * Uso: <button type="button" class="password-toggle-btn" data-target="#id_do_input" aria-label="Mostrar/ocultar senha"><i class="bi bi-eye"></i></button>
 * Funciona com input-group nativo do Bootstrap 5
 */

(function() {
    'use strict';

    function initPasswordToggles() {
        // Seleciona botões com data-target OU data-password-toggle-target (compatibilidade)
        const buttons = document.querySelectorAll('[data-target], [data-password-toggle-target]');
        
        buttons.forEach(btn => {
            // Evita inicialização dupla
            if (btn.dataset.toggleInitialized === 'true') return;
            btn.dataset.toggleInitialized = 'true';

            // Aplica estilo consistente (conforme especificação do usuário)
            applyToggleStyle(btn);

            // Evento de clique
            btn.addEventListener('click', togglePassword);
        });
    }

    function applyToggleStyle(btn) {
        // Remove classes Bootstrap que deixam feio
        btn.classList.remove('btn', 'btn-outline-secondary', 'btn-sm', 'btn-lg');
        
        // Adiciona classe customizada
        btn.classList.add('password-toggle-btn');
        
        // Estilo EXATO conforme especificação do usuário
        const style = `
            background: transparent !important;
            border: none !important;
            padding: 0 !important;
            cursor: pointer !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            margin-left: 5% !important;
            color: var(--text-muted, #64748b) !important;
            transition: color 0.15s ease !important;
            min-width: 44px !important;  /* touch target acessível */
            height: 100% !important;  /* altura total do input-group */
        `;
        btn.style.cssText = style;

        // Hover effects via JS
        btn.addEventListener('mouseenter', () => {
            btn.style.color = 'var(--semeq-navy, #0a1033)';
        });
        btn.addEventListener('mouseleave', () => {
            btn.style.color = 'var(--text-muted, #64748b)';
        });
        
        // Focus visible para acessibilidade
        btn.addEventListener('focus', () => {
            btn.style.outline = '2px solid var(--semeq-navy, #0a1033)';
            btn.style.outlineOffset = '2px';
            btn.style.borderRadius = '4px';
        });
        btn.addEventListener('blur', () => {
            btn.style.outline = 'none';
        });
    }

    function togglePassword(e) {
        const btn = e.currentTarget;
        // Aceita ambos atributos para compatibilidade
        const targetId = btn.dataset.target || btn.dataset.passwordToggleTarget;
        if (!targetId) return;

        const input = document.querySelector(targetId);
        if (!input) return;

        const isPassword = input.type === 'password';
        input.type = isPassword ? 'text' : 'password';

        // Troca ícone
        const icon = btn.querySelector('i');
        if (icon) {
            icon.classList.toggle('bi-eye', !isPassword);
            icon.classList.toggle('bi-eye-slash', isPassword);
        }

        // Atualiza aria-label
        btn.setAttribute('aria-label', isPassword ? 'Ocultar senha' : 'Mostrar senha');
    }

    // Auto-inicializa quando DOM pronto
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPasswordToggles);
    } else {
        initPasswordToggles();
    }

    // Re-inicializa em conteúdo carregado via AJAX (modais, etc.)
    document.addEventListener('htmx:afterSwap', initPasswordToggles);
    document.addEventListener('bootstrap:modal:shown', initPasswordToggles);

    // Exporta para uso manual se necessário
    window.PasswordToggle = {
        init: initPasswordToggles
    };
})();
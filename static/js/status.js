// Status inline changer para apontamentos
// Usado em: lista (/apontamentos/), dashboard e detalhe
(function () {
    'use strict';

    // Lê o token CSRF do cookie (padrão do Django)
    function getCsrfToken() {
        const name = 'csrftoken';
        const match = document.cookie.match(new RegExp('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)'));
        if (match) return match.pop();
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) return meta.getAttribute('content');
        const input = document.querySelector('[name=csrfmiddlewaretoken]');
        if (input) return input.value;
        return '';
    }

    // Mostra um toast de feedback (cria o container se necessário)
    function showStatusToast(message, type) {
        let container = document.getElementById('statusToastContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'statusToastContainer';
            container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            container.style.zIndex = '9999';
            document.body.appendChild(container);
        }
        const id = 'statusToast-' + Date.now();
        const typeClass = type === 'success' ? 'bg-success' : 'bg-danger';
        const html = `
            <div id="${id}" class="toast ${typeClass} text-white" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="toast-header">
                    <strong class="me-auto">${type === 'success' ? 'Status' : 'Erro'}</strong>
                    <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Fechar"></button>
                </div>
                <div class="toast-body">${message}</div>
            </div>`;
        container.insertAdjacentHTML('beforeend', html);
        const el = document.getElementById(id);
        if (typeof bootstrap !== 'undefined' && bootstrap.Toast) {
            const toast = new bootstrap.Toast(el, { delay: 4000 });
            toast.show();
            el.addEventListener('hidden.bs.toast', function () { el.remove(); });
        } else {
            setTimeout(function () { el.remove(); }, 4000);
        }
    }

    // Clique no badge de status -> esconde badge e mostra select
    document.addEventListener('click', function (e) {
        const badge = e.target.closest('.status-badge');
        if (badge) {
            e.stopPropagation();
            const row = badge.closest('tr');
            const select = row ? row.querySelector('.status-select') : null;
            if (select) {
                badge.classList.add('d-none');
                select.classList.remove('d-none');
                select.focus();
            }
        }
    });

    // Impede propagação de clique no select de status (evita abrir detalhes)
    document.addEventListener('click', function (e) {
        const select = e.target.closest('.status-select');
        if (select) {
            e.stopPropagation();
        }
    });

    // Blur no select -> esconde select e mostra badge
    document.addEventListener('focusout', function (e) {
        const select = e.target.closest('.status-select');
        if (select && !select.contains(e.relatedTarget)) {
            const row = select.closest('tr');
            const badge = row ? row.querySelector('.status-badge') : null;
            if (badge) {
                select.classList.add('d-none');
                badge.classList.remove('d-none');
            }
        }
    });

    // Lida com mudança de status em qualquer .status-select na página
    document.addEventListener('change', function (e) {
        const select = e.target.closest('.status-select');
        if (!select) return;
        e.stopPropagation(); // Garante que não propague
        
        const pk = select.getAttribute('data-pk');
        const previous = select.getAttribute('data-prev') || '';

        select.disabled = true;

        fetch('/apontamentos/' + pk + '/status/', {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCsrfToken()
            },
            body: new URLSearchParams({ status: select.value })
        })
            .then(function (resp) { return resp.json(); })
            .then(function (data) {
                select.disabled = false;
                select.setAttribute('data-prev', select.value);
                if (data.success) {
                    showStatusToast(data.message, 'success');
                    // Atualiza o badge
                    const row = select.closest('tr');
                    const badge = row ? row.querySelector('.status-badge') : null;
                    if (badge) {
                        const selectedOption = select.options[select.selectedIndex];
                        badge.textContent = selectedOption.text;
                        badge.setAttribute('data-status', select.value);
                        // Nota: cor seria atualizada via reload ou AJAX extra
                    }
                } else {
                    select.value = previous || '';
                    showStatusToast(data.message || 'Erro ao atualizar status.', 'danger');
                }
                // Esconde select e mostra badge
                select.classList.add('d-none');
                const row = select.closest('tr');
                const badge = row ? row.querySelector('.status-badge') : null;
                if (badge) {
                    badge.classList.remove('d-none');
                }
            })
            .catch(function () {
                select.disabled = false;
                select.value = previous || '';
                showStatusToast('Erro de conexão ao atualizar status.', 'danger');
                select.classList.add('d-none');
                const row = select.closest('tr');
                const badge = row ? row.querySelector('.status-badge') : null;
                if (badge) {
                    badge.classList.remove('d-none');
                }
            });
    });
})();

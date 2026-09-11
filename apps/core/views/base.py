from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy


class PermissionMixin:
    """Apenas Admin e Gestor podem gerenciar."""
    def dispatch(self, request, *args, **kwargs):
        perfil = getattr(request.user, 'perfil', None)
        if not (request.user.is_authenticated and (request.user.is_superuser or (perfil and perfil.is_gestor_or_above()))):
            messages.error(request, 'Acesso negado. Apenas administradores e gestores.')
            return redirect('semeq:dashboard')
        return super().dispatch(request, *args, **kwargs)


# =====================================================================
# BASE CRUD VIEWS
# =====================================================================

class BaseCRUDListView(LoginRequiredMixin, ListView):
    model = None
    template_name = None
    context_object_name = 'object_list'
    search_fields = []
    paginate_by = 20

    def get_queryset(self):
        qs = self.model.objects.all()
        
        # Search
        q = self.request.GET.get('q', '').strip()
        if q and self.search_fields:
            from django.db.models import Q
            query = Q()
            for field in self.search_fields:
                query |= Q(**{f"{field}__icontains": q})
            qs = qs.filter(query)
        
        # Ordering
        ordering = getattr(self.model._meta, 'ordering', ['-criado_em'])
        if ordering:
            qs = qs.order_by(*ordering)
        
        return qs
    
    def get_context_data(self, **kwargs):
        q = self.request.GET.get('q', '').strip()
        page = self.request.GET.get('page', 1)
        
        from django.core.paginator import Paginator
        qs = self.get_queryset()
        paginator = Paginator(qs, self.paginate_by)
        page_obj = paginator.get_page(page)
        
        context = super().get_context_data(**kwargs)
        context.update({
            'page_obj': page_obj,
            'object_list': page_obj.object_list,
            'search': q,
            'title': getattr(self, 'title', self.model._meta.verbose_name_plural.title()),
            'icon': getattr(self, 'icon', ''),
            'create_url': reverse_lazy(self.create_url_name) if getattr(self, 'create_url_name', None) else None,
            'import_url': reverse_lazy(self.import_url_name) if getattr(self, 'import_url_name', None) else None,
            'edit_url_name': getattr(self, 'edit_url_name', None),
            'delete_url_name': getattr(self, 'delete_url_name', None),
            'create_label': getattr(self, 'create_label', self.model._meta.verbose_name),
            'current_tab': getattr(self, 'current_tab', ''),
        })
        return context


class BaseCRUDCreateView(LoginRequiredMixin, CreateView):
    model = None
    form_class = None
    template_name = None
    success_url = None

    def form_valid(self, form):
        messages.success(self.request, f'{self.model._meta.verbose_name} criado com sucesso!')
        return super().form_valid(form)


class BaseCRUDUpdateView(LoginRequiredMixin, UpdateView):
    model = None
    form_class = None
    template_name = None
    success_url = None

    def form_valid(self, form):
        messages.success(self.request, f'{self.model._meta.verbose_name} atualizado com sucesso!')
        return super().form_valid(form)


class BaseCRUDDeleteView(LoginRequiredMixin, DeleteView):
    model = None
    template_name = None
    success_url = None
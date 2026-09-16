with open('user/views.py', 'rb') as f:
    content = f.read()

# Normalize line endings
content = content.replace(b'\r\n', b'\n')

# Fix the get_context_data method
old = b'    def get_context_data(self, **kwargs):\n        context = super().get_context_data(**kwargs)\n        # Count related apontamentos\n        from user.models import Apontamento\n        user = self.object\n        context["apontamentos_count"] = Apontamento.objects.filter(responsavel=user).count()\n        # Check if current user is admin or gestor\n        perfil = self.request.user.perfil if hasattr(self.request.user, "perfil") else None\n        context["is_admin"] = self.request.user.is_superuser or (perfil and perfil.is_admin())\n        context["is_admin_or_gestor"] = self.request.user.is_superuser or (perfil and perfil.is_gestor_or_above())\n        context["show_delete_apontamentos_checkbox"] = context["is_admin_or_gestor"] and context["apontamentos_count"] > 0\n        return context'

new = b'    def get_context_data(self, **kwargs):\n        context = super().get_context_data(**kwargs)\n        # Count related apontamentos\n        from user.models import Apontamento\n        user = self.object\n        context["apontamentos_count"] = Apontamento.objects.filter(responsavel=user).count()\n        # Check if current user is admin or gestor\n        perfil = self.request.user.perfil if hasattr(self.request.user, "perfil") else None\n        context["is_admin"] = self.request.user.is_superuser or (perfil and perfil.is_admin())\n        context["is_admin_or_gestor"] = self.request.user.is_superuser or (perfil and perfil.is_gestor_or_above())\n        context["show_delete_apontamentos_checkbox"] = context["is_admin_or_gestor"] and context["apontamentos_count"] > 0\n        return context'

if old in content:
    content = content.replace(old, new)
    print('Replaced')
else:
    print('Not found')

with open('user/views.py', 'wb') as f:
    f.write(content)
print('Done')
from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordResetForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import Cliente, Equipamento, PerfilUsuario, Time, Apontamento


class EquipamentoForm(forms.ModelForm):
    class Meta:
        model = Equipamento
        fields = [
            'tipo',
            'modelo', 'descricao',
        ]
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            'corporation_id', 'corporation', 'plant_id', 'plant',
            'zone'
        ]
        widgets = {
            'corporation_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: BR001'}),
            'corporation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: SEMEQ Brasil'}),
            'plant_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: SP001'}),
            'plant': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: São Paulo'}),
            'zone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Zona 1'})
        }

    def clean_corporation_id(self):
        corp_id = self.cleaned_data['corporation_id'].strip().upper()
        if not corp_id:
            raise ValidationError('ID Corporação é obrigatório.')
        return corp_id

    def clean_plant_id(self):
        plant_id = self.cleaned_data['plant_id'].strip().upper()
        if not plant_id:
            raise ValidationError('ID Planta é obrigatório.')
        return plant_id

    def clean(self):
        cleaned_data = super().clean()
        corp_id = cleaned_data.get('corporation_id')
        plant_id = cleaned_data.get('plant_id')
        
        if corp_id and plant_id:
            qs = Cliente.objects.filter(corporation_id=corp_id, plant_id=plant_id)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(
                    'Já existe um cliente com esta combinação de Corporation ID e Plant ID.'
                )
        return cleaned_data


class ClienteImportForm(forms.Form):
    arquivo = forms.FileField(
        label='Arquivo (CSV ou Excel)',
        help_text='Colunas esperadas: corporation_id, corporation, plant_id, plant, unat, city, state_province, country, region, business, zone',
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.csv,.xlsx,.xls'})
    )
    atualizar_existentes = forms.BooleanField(
        label='Atualizar clientes existentes',
        required=False,
        initial=True,
        help_text='Se marcado, atualiza clientes com mesmo corporation_id + plant_id. Se desmarcado, ignora duplicados.',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def clean_arquivo(self):
        arquivo = self.cleaned_data['arquivo']
        ext = arquivo.name.lower().split('.')[-1]
        if ext not in ['csv', 'xlsx', 'xls']:
            raise ValidationError('Formato inválido. Use CSV ou Excel (.xlsx, .xls).')
        return arquivo


class UsuarioForm(forms.ModelForm):
    password = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
        help_text='Mínimo 8 caracteres.'
    )
    password_confirm = forms.CharField(
        label='Confirmar Senha',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )
    role = forms.ChoiceField(
        choices=PerfilUsuario.ROLE_CHOICES,
        label='Função',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    telefone = forms.CharField(
        label='Telefone',
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(11) 99999-9999'})
    )
    time = forms.ModelChoiceField(
        queryset=Time.objects.filter(ativo=True),
        label='Time',
        required=False,
        empty_label='--- Selecione ---',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: joao.silva'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: João'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Silva'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Ex: joao@empresa.com'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and not user.is_superuser:
            # Non-admin cannot create admin users
            self.fields['role'].choices = [c for c in PerfilUsuario.ROLE_CHOICES if c[0] != 'admin']

    def clean_username(self):
        username = self.cleaned_data['username'].strip().lower()
        if User.objects.filter(username__iexact=username).exclude(pk=self.instance.pk).exists():
            raise ValidationError('Este nome de usuário já está em uso.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError('Este e-mail já está cadastrado.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        
        if password and password_confirm:
            if password != password_confirm:
                raise ValidationError({'password_confirm': 'As senhas não coincidem.'})
            if len(password) < 8:
                raise ValidationError({'password': 'A senha deve ter no mínimo 8 caracteres.'})
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            PerfilUsuario.objects.create(
                user=user,
                role=self.cleaned_data['role'],
                telefone=self.cleaned_data['telefone'],
                time=self.cleaned_data['time'],
            )
        return user


class UsuarioUpdateForm(forms.ModelForm):
    role = forms.ChoiceField(
        choices=PerfilUsuario.ROLE_CHOICES,
        label='Função',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    telefone = forms.CharField(
        label='Telefone',
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(11) 99999-9999'})
    )
    time = forms.ModelChoiceField(
        queryset=Time.objects.filter(ativo=True),
        label='Time',
        required=False,
        empty_label='--- Selecione ---',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    ativo = forms.BooleanField(
        label='Ativo',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)
        
        # Get or create perfil
        perfil, _ = PerfilUsuario.objects.get_or_create(user=self.instance)
        
        # Set initial values from perfil
        self.fields['role'].initial = perfil.role
        self.fields['telefone'].initial = perfil.telefone
        self.fields['time'].initial = perfil.time
        self.fields['ativo'].initial = perfil.ativo
        
        # Non-superusers cannot edit admin users or promote to admin
        if self.request_user and not self.request_user.is_superuser:
            target_perfil = getattr(self.instance, 'perfil', None)
            if target_perfil and target_perfil.is_admin():
                # Disable all fields for admin users
                for field in self.fields.values():
                    field.disabled = True
            else:
                # Cannot promote to admin
                self.fields['role'].choices = [c for c in PerfilUsuario.ROLE_CHOICES if c[0] != 'admin']
        
        # Users cannot edit themselves (prevent privilege escalation)
        if self.request_user and self.request_user == self.instance:
            self.fields['role'].disabled = True
            self.fields['is_active'].disabled = True

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            perfil, _ = PerfilUsuario.objects.get_or_create(user=user)
            perfil.role = self.cleaned_data['role']
            perfil.telefone = self.cleaned_data['telefone']
            perfil.time = self.cleaned_data['time']
            perfil.ativo = self.cleaned_data['ativo']
            perfil.save()
        return user


class ApontamentoForm(forms.ModelForm):
    # Extra field: checkbox to allow changing the planta
    alterar_planta = forms.BooleanField(
        label='Alterar planta',
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_alterar_planta'}),
        help_text='Marque para alterar a planta do apontamento'
    )

    class Meta:
        model = Apontamento
        fields = [
            'cliente', 'projeto', 'solicitante', 'ticket', 'equipamento',
            'prioridade', 'equipe', 'responsavel', 'atividade', 'tipo_problema',
            'status', 'data', 'hora_inicial', 'hora_final',
            'apos_18h',
            'gw_ar', 'desvio', 'descricao'
        ]
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-select cliente-select', 'id': 'id_cliente'}),
            'projeto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome/ID do projeto'}),
            'solicitante': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do solicitante'}),
            'ticket': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: INC123456'}),
            'equipamento': forms.Select(attrs={'class': 'form-select equipamento-select'}),
            'prioridade': forms.Select(attrs={'class': 'form-select'}),
            'equipe': forms.Select(attrs={'class': 'form-select'}),
            'responsavel': forms.Select(attrs={'class': 'form-select responsavel-select'}),
            'atividade': forms.Select(attrs={'class': 'form-select'}),
            'tipo_problema': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'data': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'max': ''}),
            'hora_inicial': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'hora_final': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'gw_ar': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'apos_18h': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'desvio': forms.Select(attrs={'class': 'form-select'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Descreva o apontamento...'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set default values
        from datetime import date
        self.fields['data'].initial = date.today()
        
        # If editing existing instance, disable cliente by default (unless alterar_planta is checked)
        if self.instance and self.instance.pk:
            self.fields['cliente'].disabled = True
            # Store original cliente for reference
            self.original_cliente = self.instance.cliente
            # Set initial for alterar_planta based on POST data or leave as False
        else:
            self.original_cliente = None
        
        # If user is not admin/gestor, hide/limit responsavel field
        if self.user:
            perfil = getattr(self.user, 'perfil', None)
            if perfil and not perfil.is_gestor_or_above():
                # Colaborador/Líder: só pode apontar para si mesmo
                self.fields['responsavel'].queryset = User.objects.filter(id=self.user.id)
                self.fields['responsavel'].initial = self.user
                self.fields['responsavel'].widget = forms.HiddenInput()
                self.fields['responsavel'].required = False
            elif perfil and perfil.is_lider_or_above() and not perfil.is_gestor_or_above():
                # Líder: pode apontar para usuários do seu time
                qs = User.objects.filter(
                    perfil__time=perfil.time, perfil__ativo=True
                ).select_related('perfil')
                self.fields['responsavel'].queryset = qs
                self.fields['responsavel'].initial = qs.first()
            else:
                # Gestor/Admin: pode apontar para qualquer usuário ativo
                qs = User.objects.filter(
                    perfil__ativo=True
                ).select_related('perfil').order_by('first_name', 'last_name')
                self.fields['responsavel'].queryset = qs
                self.fields['responsavel'].initial = qs.first()
        
        # Cliente queryset
        self.fields['cliente'].queryset = Cliente.objects.all().order_by('corporation', 'plant')
        self.fields['cliente'].required = False
        
        # Equipamento queryset (filtered by cliente via JS)
        self.fields['equipamento'].queryset = Equipamento.objects.all().order_by('tipo', 'modelo')

        # Remove empty_label from ModelChoiceFields so first option is selected by default
        for field_name in ['responsavel', 'equipamento']:
            if field_name in self.fields and hasattr(self.fields[field_name], 'empty_label'):
                self.fields[field_name].empty_label = None

        # For ChoiceFields (CharField with choices), remove blank choice by setting choices directly
        from .models import Apontamento
        choice_fields = {
            'equipe': Apontamento.EQUIPE_CHOICES,
            'atividade': Apontamento.ATIVIDADE_CHOICES,
            'tipo_problema': Apontamento.TIPO_PROBLEMA_CHOICES,
            'status': Apontamento.STATUS_CHOICES,
            'prioridade': Apontamento.PRIORIDADE_CHOICES,
            'desvio': Apontamento.DESVIO_CHOICES,
        }
        for field_name, choices in choice_fields.items():
            if field_name in self.fields:
                self.fields[field_name].choices = choices
                # Set initial to first choice if no default exists on model
                if not self.fields[field_name].initial and choices:
                    self.fields[field_name].initial = choices[0][0]

    def clean(self):
        cleaned_data = super().clean()
        hora_inicial = cleaned_data.get('hora_inicial')
        hora_final = cleaned_data.get('hora_final')
        data = cleaned_data.get('data')
        responsavel = cleaned_data.get('responsavel')
        alterar_planta = cleaned_data.get('alterar_planta', False)
        
        # Handle cliente field logic
        if self.instance.pk and not alterar_planta:
            # Not changing plant: always use original cliente (ignore form data)
            cleaned_data['cliente'] = self.instance.cliente
        elif alterar_planta:
            # Changing plant: get cliente from raw form data (not from cleaned_data which has instance value)
            cliente_raw = self.data.get('cliente')
            if not cliente_raw:
                self.add_error('cliente', 'Selecione uma planta ao alterar a planta.')
            else:
                try:
                    from .models import Cliente
                    cliente = Cliente.objects.get(pk=cliente_raw)
                    if cliente == self.instance.cliente:
                        self.add_error('cliente', 'Selecione uma planta diferente da atual.')
                    else:
                        cleaned_data['cliente'] = cliente
                except (Cliente.DoesNotExist, ValueError):
                    self.add_error('cliente', 'Planta selecionada inválida.')
        
        # Require time fields
        has_times = hora_inicial and hora_final
        
        if not has_times:
            raise ValidationError(
                'Preencha Hora Inicial e Hora Final.'
            )
        
        if has_times:
            if hora_final <= hora_inicial:
                raise ValidationError({
                    'hora_final': 'Hora final deve ser posterior à hora inicial.'
                })
        
        # Check for overlapping apontamentos for same responsavel + data
        if responsavel and data:
            qs = Apontamento.objects.filter(
                responsavel=responsavel,
                data=data
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            
            # Check overlap only if we have time fields
            if has_times:
                for ap in qs:
                    if ap.hora_inicial and ap.hora_final:
                        if not (hora_final <= ap.hora_inicial or hora_inicial >= ap.hora_final):
                            raise ValidationError(
                                f'Já existe apontamento para {responsavel.get_full_name() or responsavel.username} '
                                f'neste horário ({ap.hora_inicial}-{ap.hora_final}).'
                            )
        
        return cleaned_data


class PublicRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'seu@email.com'})
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome'})
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Sobrenome'})
    )
    telefone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(11) 99999-9999'})
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome de usuário'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Senha'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Confirmar senha'})

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('Este e-mail já está cadastrado.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.is_active = False  # Requires admin approval
        if commit:
            user.save()
            PerfilUsuario.objects.create(
                user=user,
                role='usuario',
                telefone=self.cleaned_data['telefone'],
                ativo=False,  # Inactive until approved
            )
        return user


class SemeqPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(
        label='E-mail',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Digite seu e-mail cadastrado',
            'autocomplete': 'email'
        })
    )

    def get_users(self, email):
        """Override to only return active users with perfil ativo"""
        from django.contrib.auth import get_user_model
        UserModel = get_user_model()
        return UserModel._default_manager.filter(
            email__iexact=email,
            is_active=True,
            perfil__ativo=True
        )
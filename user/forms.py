from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordResetForm, AuthenticationForm, PasswordChangeForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone
from datetime import timedelta, date
from .models import Cliente, Equipamento, PerfilUsuario, Time, Apontamento, EmailVerificationToken, Status, Atividade, Prioridade, TipoProblema, Equipe, Projeto, Solicitante, ApontamentoTempo

# Today's date for max attribute on date inputs
today_str = date.today().isoformat()


class EquipamentoForm(forms.ModelForm):
    class Meta:
        model = Equipamento
        fields = [
            'tipo', 'device', 'modelo', 'ativo',
        ]
        widgets = {
            'tipo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Gateway, Bomba, Sensor...', 'list': 'dl-tipo-equipamento', 'autocomplete': 'off'}),
            'device': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Serial Number ou Tag'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Model X1'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input form-switch'}),
        }


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            'corporation',  'plant', 'zone', 'ativo'
        ]
        widgets = {
            'corporation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: SEMEQ Brasil'}),
            'plant': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: São Paulo'}),
            'zone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Zona 1'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input form-switch'}),
        }


    def clean(self):
        cleaned_data = super().clean()
        corp =  cleaned_data.get('corporation')
        plant = cleaned_data.get('plant')
    
        if corp and plant:
            qs = Cliente.objects.filter(corporation=corp, plant=plant)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(
                    'Já existe um cliente com esta combinação de Corporação e Planta.'
                )
        return cleaned_data


class ClienteImportForm(forms.Form):
    arquivo = forms.FileField(
        label='Arquivo (CSV ou Excel)',
        help_text='Colunas esperadas: corporation, plant, zone (opcional: corporation_id, plant_id)',
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.csv,.xlsx,.xls'})
    )
    atualizar_existentes = forms.BooleanField(
        label='Atualizar clientes existentes',
        required=False,
        initial=True,
        help_text='Se marcado, atualiza clientes com mesma corporação + planta. Se desmarcado, ignora duplicados.',
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
    equipe = forms.ModelChoiceField(
        queryset=Equipe.objects.filter(ativo=True),
        label='Equipe',
        required=False,
        empty_label='--- Selecione ---',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    ativo = forms.BooleanField(
        label='Ativo',
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
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

    def clean_email(self):
        from user.backends import normalize_email
        email = normalize_email(self.cleaned_data['email'])
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError('Este e-mail já está cadastrado.')
        return email.lower()

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
        # Normalize email to lowercase
        email = self.cleaned_data['email'].strip().lower()
        base_username = email.split('@')[0].lower()
        base_username = ''.join(c for c in base_username if c.isalnum() or c in '._-')
    
        username = base_username
        counter = 1
        while User.objects.filter(username__iexact=username).exclude(pk=self.instance.pk).exists():
            username = f"{base_username}{counter}"
            counter += 1
    
        user.username = username
        user.email = email  # Save normalized email
        user.is_active = self.cleaned_data.get('ativo', True)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            PerfilUsuario.objects.create(
                user=user,
                role=self.cleaned_data['role'],
                telefone=self.cleaned_data['telefone'],
                equipe=self.cleaned_data['equipe'],
                ativo=self.cleaned_data.get('ativo', True),
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
    equipe = forms.ModelChoiceField(
        queryset=Equipe.objects.filter(ativo=True),
        label='Equipe',
        required=False,
        empty_label='--- Selecione ---',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    ativo = forms.BooleanField(
        label='Ativo',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    password = forms.CharField(
        label='Nova Senha (opcional)',
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
        help_text='Deixe em branco para manter a senha atual. Mínimo 8 caracteres.'
    )
    password_confirm = forms.CharField(
        label='Confirmar Nova Senha',
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)
    
        # Get or create perfil
        perfil, _ = PerfilUsuario.objects.get_or_create(user=self.instance)
    
        # Set initial values from perfil
        self.fields['role'].initial = perfil.role
        self.fields['telefone'].initial = perfil.telefone
        self.fields['equipe'].initial = perfil.equipe
        self.fields['ativo'].initial = perfil.ativo
    
        # Non-superusers cannot edit admin users' role/active status, but CAN change their team
        if self.request_user and not self.request_user.is_superuser:
            target_perfil = getattr(self.instance, 'perfil', None)
            if target_perfil and target_perfil.is_admin():
                # Disable role and active fields for admin users, but allow equipe change
                self.fields['role'].disabled = True
                self.fields['ativo'].disabled = True
            else:
                # Cannot promote to admin
                self.fields['role'].choices = [c for c in PerfilUsuario.ROLE_CHOICES if c[0] != 'admin']
    
        # Users cannot edit themselves (prevent privilege escalation)
        if self.request_user and self.request_user == self.instance:
            self.fields['role'].disabled = True
            self.fields['ativo'].disabled = True

    def clean_email(self):
        from user.backends import normalize_email
        email = normalize_email(self.cleaned_data['email'])
    
        # Only check for duplicates if email is actually being changed
        current_email = self.instance.email
        if current_email and normalize_email(current_email) == email:
            return email.lower()
    
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError('Este e-mail já está cadastrado.')
        return email.lower()

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
    
        if password or password_confirm:
            if password != password_confirm:
                raise ValidationError({'password_confirm': 'As senhas não coincidem.'})
            if len(password) < 8:
                raise ValidationError({'password': 'A senha deve ter no mínimo 8 caracteres.'})
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            # Update password if provided
            password = self.cleaned_data.get('password')
            if password:
                user.set_password(password)
                user.save()
            perfil, _ = PerfilUsuario.objects.get_or_create(user=user)
            perfil.role = self.cleaned_data['role']
            perfil.telefone = self.cleaned_data['telefone']
            perfil.equipe = self.cleaned_data['equipe']
            perfil.ativo = self.cleaned_data['ativo']
            perfil.save()
            # Sync User.is_active with PerfilUsuario.ativo
            user.is_active = perfil.ativo
            user.save(update_fields=['is_active'])
        return user


class ApontamentoForm(forms.ModelForm):
    # Extra fields for "Outro" options in select dropdowns
    outro_atividade = forms.CharField(
        label='Outra Atividade',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Descreva a atividade...'})
    )
    outro_tipo_problema = forms.CharField(
        label='Outro Tipo de Problema',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Descreva o tipo de problema...'})
    )
    outro_equipamento_descricao = forms.CharField(
        label='Outro Equipamento',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Descreva o equipamento...'})
    )

    class Meta:
        model = Apontamento
        # Ordem: Projeto, Atividade, Solicitante, Cliente, ID (auto) + demais
        # ticket fora: gerado automaticamente, sem input manual
        fields = [
            'projeto', 'atividade', 'solicitante', 'cliente', 'equipamento',
            'prioridade', 'equipe', 'responsavel', 'tipo_problema',
            'status', 'data_inicial', 'data_final', 'tempo_investido_minutos', 'descricao'
        ]
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-select cliente-select', 'id': 'id_cliente'}),
            'projeto': forms.Select(attrs={'class': 'form-select'}),
            'solicitante': forms.Select(attrs={'class': 'form-select'}),
            'ticket': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: INC123456'}),
            'equipamento': forms.Select(attrs={'class': 'form-select equipamento-select'}),
            'prioridade': forms.Select(attrs={'class': 'form-select'}),
            'equipe': forms.Select(attrs={'class': 'form-select', 'id': 'id_equipe'}),
            'responsavel': forms.Select(attrs={'class': 'form-select responsavel-select', 'id': 'id_responsavel'}),
            'atividade': forms.Select(attrs={'class': 'form-select'}),
            'tipo_problema': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'data_inicial': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'max': today_str}, format='%Y-%m-%d'),
            'data_final': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'max': today_str}, format='%Y-%m-%d'),
            'tempo_investido_minutos': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'autocomplete': 'off'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Descreva o apontamento...'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Equipamento "Outro": o select envia '__outro__' + descrição livre.
        # Troca pelo vazio antes da validação do ModelChoiceField e guarda a
        # descrição para criar o Equipamento(tipo='outro') no clean().
        self._equipamento_outro = False
        self._outro_equip_desc = ''
        if self.data and self.data.get('equipamento') == '__outro__':
            self._equipamento_outro = True
            self._outro_equip_desc = (self.data.get('outro_equipamento_descricao') or '').strip()
            data = self.data.copy()
            data['equipamento'] = ''
            self.data = data
        
        # Add max_value validator to tempo_investido_minutos (PostgreSQL integer max = 2147483647)
        from django.core.validators import MaxValueValidator
        self.fields['tempo_investido_minutos'].validators.append(
            MaxValueValidator(2147483647, 'O tempo investido não pode exceder 2.147.483.647 minutos.')
        )
    
        # Set default values for NEW apontamentos only
        from datetime import date
        today = date.today()
        if not (self.instance and self.instance.pk):
            self.fields['data_inicial'].initial = today
    
        if self.instance and self.instance.pk:
            self.original_cliente = self.instance.cliente
            # Allow editing cliente directly - no disabled state
            self.fields['cliente'].disabled = False
        else:
            self.original_cliente = None
    
        # Cliente queryset
        self.fields['cliente'].queryset = Cliente.objects.all().order_by('corporation', 'plant')
        self.fields['cliente'].required = False
    
        # Projeto queryset
        self.fields['projeto'].queryset = Projeto.objects.filter(ativo=True).order_by('nome')
        self.fields['projeto'].required = False
    
        # Solicitante queryset
        self.fields['solicitante'].queryset = Solicitante.objects.filter(ativo=True).order_by('nome')
        self.fields['solicitante'].required = False
    
        # Equipamento queryset (filtered by cliente via JS)
        self.fields['equipamento'].queryset = Equipamento.objects.all().order_by('tipo', 'device', 'modelo')

        # Remove empty_label from ModelChoiceFields so first option is selected by default
        for field_name in ['cliente', 'projeto', 'solicitante', 'responsavel', 'equipamento', 'equipe', 'atividade', 'tipo_problema', 'status', 'prioridade']:
            if field_name in self.fields and hasattr(self.fields[field_name], 'empty_label'):
                self.fields[field_name].empty_label = None

        # Make equipe required for all users
        self.fields['equipe'].required = True
    
# ============================================================
        # CONTROLE DE ACESSO POR PERFIL (Equipe & Responsável)
        # ============================================================
        if self.user:
            perfil = getattr(self.user, 'perfil', None)
        
            if perfil:
                is_admin_or_gestor = perfil.is_gestor_or_above()
                is_lider = perfil.is_lider_or_above() and not perfil.is_gestor_or_above()
                is_colaborador = perfil.is_colaborador()
                user_equipe = perfil.equipe
            
                # --- CAMPO EQUIPE ---
                # SEMPRE define a equipe inicial como a do usuário logado
                # OCULTA o campo para todos os usuários (cada usuário só aponta para sua equipe)
                if user_equipe:
                    self.fields['equipe'].initial = user_equipe
            
                # Para todos os usuários: equipe oculta/fixa na sua equipe
                if user_equipe:
                    self.fields['equipe'].queryset = Equipe.objects.filter(pk=user_equipe.pk)
                    # Use HiddenInput so value is submitted but not visible
                    self.fields['equipe'].widget = forms.HiddenInput()
                    self.fields['equipe'].required = True
                    self.fields['equipe'].disabled = False
            
                # --- CAMPO RESPONSÁVEL ---
                # REGRA ESTRITA: cada usuário só cria/aponta para si mesmo
                self.fields['responsavel'].queryset = User.objects.filter(id=self.user.id)
                self.fields['responsavel'].initial = self.user
                self.fields['responsavel'].widget = forms.HiddenInput()
                self.fields['responsavel'].required = False
                self.fields['responsavel'].disabled = False

    def clean_tempo_investido_minutos(self):
        """Ensure empty string is converted to 0 or None to allow saving.
        Also validate that the value doesn't exceed PostgreSQL integer max (2147483647)."""
        value = self.cleaned_data.get('tempo_investido_minutos')
        if value == '' or value is None:
            return 0
        # Validate upper bound (PostgreSQL integer max = 2147483647)
        if value > 2147483647:
            from django.core.exceptions import ValidationError
            raise ValidationError('O tempo investido não pode exceder 2.147.483.647 minutos.')
        return value

    def clean(self):
        cleaned_data = super().clean()
        # Equipamento "Outro": cria (ou reutiliza) Equipamento tipo=outro
        # com a descrição digitada, em vez de falhar na validação do select.
        if getattr(self, '_equipamento_outro', False):
            if not self._outro_equip_desc:
                self.add_error(
                    'outro_equipamento_descricao',
                    'Descreva o equipamento ao selecionar "Outro".'
                )
            else:
                equipamento, _ = Equipamento.objects.get_or_create(
                    tipo='outro',
                    device=self._outro_equip_desc[:100],
                    defaults={'modelo': ''},
                )
                cleaned_data['equipamento'] = equipamento
        data_inicial = cleaned_data.get('data_inicial')
        data_final = cleaned_data.get('data_final')
        tempo_investido_minutos = cleaned_data.get('tempo_investido_minutos')
        responsavel = cleaned_data.get('responsavel')
    
        # Ensure tempo_investido_minutos has a default value (0) to avoid NOT NULL constraint issues
        if tempo_investido_minutos is None:
            cleaned_data['tempo_investido_minutos'] = 0
            tempo_investido_minutos = 0
    
        # Handle cliente field logic - allow editing directly
        if self.instance.pk:
            novo_cliente = cleaned_data.get('cliente')
            if not novo_cliente:
                self.add_error('cliente', 'Selecione uma planta.')
            else:
                cleaned_data['cliente'] = novo_cliente
        elif not self.instance.pk:
            # New apontamento: get cliente from form data
            cliente_raw = self.data.get('cliente') or self.data.get('cliente_id')
            if not cliente_raw:
                # Try to get from cleaned_data
                cliente_raw = cleaned_data.get('cliente')
            if not cliente_raw:
                self.add_error('cliente', 'Selecione uma planta.')
            else:
                try:
                    from .models import Cliente
                    cliente = Cliente.objects.get(pk=cliente_raw)
                    cleaned_data['cliente'] = cliente
                except (Cliente.DoesNotExist, ValueError):
                    self.add_error('cliente', 'Planta selecionada inválida.')
    
        # Validate date fields
        from datetime import date
        today = date.today()
    
        if not data_inicial:
            raise ValidationError({'data_inicial': 'Data é obrigatória.'})
    
# Block future dates
        if data_inicial > today:
            raise ValidationError({'data_inicial': 'Não é possível criar apontamentos em datas futuras.'})
    
        if data_final:
            if data_final > today:
                raise ValidationError({'data_final': 'Não é possível criar apontamentos em datas futuras.'})
            if data_final < data_inicial:
                raise ValidationError({'data_final': 'Data final não pode ser anterior à data inicial.'})
    
        # Validate Concluído status requires tempo_investido_minutos > 0
        status = cleaned_data.get('status')
        if status and status.is_concluido_fixo:
            if not tempo_investido_minutos or tempo_investido_minutos <= 0:
                raise ValidationError({
                    'tempo_investido_minutos': 'Para concluir o apontamento, o Tempo Investido deve ser maior que 0 minutos.'
                })

        # Ensure equipe is always set (fallback to user's profile equipe)
        if not cleaned_data.get('equipe') and self.user:
            perfil = getattr(self.user, 'perfil', None)
            if perfil and perfil.equipe:
                cleaned_data['equipe'] = perfil.equipe

        return cleaned_data


class EmailLoginForm(AuthenticationForm):
    """
    Form de login usando email em vez de username.
    Compatível com EmailBackend.
    """
    username = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'seu@email.com',
            'autocomplete': 'email'
        })
    )
    password = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Sua senha',
            'autocomplete': 'current-password'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove o help_text padrão do Django
        self.fields['password'].help_text = ''


class PublicRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'seu@semeq.com'})
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
        fields = ['first_name', 'last_name', 'email', 'password1', 'password2']
        widgets = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Senha (mín. 8 caracteres)'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Confirmar senha'})

    def clean_email(self):
        from user.backends import normalize_email
        email = normalize_email(self.cleaned_data['email'])
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('Este e-mail já está cadastrado.')
    
        # Validar domínio permitido
        domain = email.split('@')[-1].lower()
        allowed_domains = getattr(settings, 'ALLOWED_EMAIL_DOMAINS', ['semeq.com'])
        if domain not in allowed_domains:
            raise ValidationError(
                f'Email não permitido. Domínios aceitos: {", ".join(allowed_domains)}'
            )
        return email.lower()

    def save(self, commit=True):
        # Gerar username único baseado no email
        email = self.cleaned_data['email'].strip().lower()
        base_username = email.split('@')[0].lower()
        base_username = ''.join(c for c in base_username if c.isalnum() or c in '._-')
    
        username = base_username
        counter = 1
        while User.objects.filter(username__iexact=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
    
        user = super().save(commit=False)
        user.username = username
        user.email = email  # Save normalized email
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.is_active = True  # Ativo por padrão, sem verificação de email
    
        if commit:
            user.save()
            PerfilUsuario.objects.create(
                user=user,
                role='colaborador',
                telefone=self.cleaned_data['telefone'],
                ativo=True,  # Ativo por padrão
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

    def clean_email(self):
        from user.backends import normalize_email
        email = normalize_email(self.cleaned_data['email'])
    
        # Validar domínio permitido
        domain = email.split('@')[-1].lower()
        allowed_domains = getattr(settings, 'ALLOWED_EMAIL_DOMAINS', ['semeq.com'])
        if domain not in allowed_domains:
            raise ValidationError(
                f'Email não permitido. Domínios aceitos: {", ".join(allowed_domains)}'
            )
        return email.lower()

    def get_users(self, email):
        """Override to only return active users with perfil ativo"""
        from django.contrib.auth import get_user_model
        UserModel = get_user_model()
        return UserModel._default_manager.filter(
            email__iexact=email,
            is_active=True,
            perfil__ativo=True
        )


class SemeqPasswordChangeForm(PasswordChangeForm):
    """Form para mudança de senha (usa senha atual + nova senha)"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Aplicar classes Bootstrap
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})
            if field_name == 'old_password':
                field.widget.attrs['placeholder'] = 'Senha atual'
            elif field_name == 'new_password1':
                field.widget.attrs['placeholder'] = 'Nova senha (mín. 8 caracteres)'
            elif field_name == 'new_password2':
                field.widget.attrs['placeholder'] = 'Confirmar nova senha'


class StatusForm(forms.ModelForm):
    class Meta:
        model = Status
        fields = [
            'status', 'cor', 'ordem', 'ativo', 'is_concluido'
        ]
        widgets = {
            'status': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Concluído'}),
            'cor': forms.TextInput(attrs={'class': 'form-control form-control-color', 'type': 'color', 'title': 'Escolha a cor'}),
            'ordem': forms.NumberInput(attrs={'class': 'form-control'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_concluido': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Se for status fixo, desabilita edição do nome e is_concluido
        if self.instance and self.instance.pk and self.instance.is_fixo:
            self.fields['status'].disabled = True
            self.fields['status'].help_text = 'Status fixo do sistema - não pode ser alterado'
            self.fields['is_concluido'].disabled = True
            self.fields['is_concluido'].help_text = 'Status fixo do sistema - não pode ser alterado'
            # Status fixos devem permanecer ativos
            self.fields['ativo'].disabled = True
            self.fields['ativo'].help_text = 'Status fixo do sistema - não pode ser desativado'

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
    
        if status:
            # Comparacao case-insensitive: 'aberto' e 'Aberto' sao o mesmo status
            qs = Status.objects.filter(status__iexact=status.strip())
        
            if self.instance.pk:
                # Verifica se já existe (exceto o próprio)
                if qs.exclude(pk=self.instance.pk).exists():
                    raise forms.ValidationError({'status': 'Já existe um status com este nome.'})
            else:
                if qs.exists():
                    raise forms.ValidationError({'status': 'Já existe um status com este nome.'})
    
        # Se for status fixo, garantir que campos protegidos não foram alterados
        if self.instance and self.instance.pk and self.instance.is_fixo:
            if 'status' in self.changed_data:
                self.add_error('status', 'Status fixo do sistema não pode ser alterado.')
            if 'is_concluido' in self.changed_data:
                self.add_error('is_concluido', 'Status fixo do sistema não pode ser alterado.')
            if 'ativo' in self.changed_data:
                self.add_error('ativo', 'Status fixo do sistema não pode ser desativado.')

        return cleaned_data


class ApontamentoTempoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.atendimento = kwargs.pop('apontamento', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    class Meta:
        model = ApontamentoTempo
        fields = ['data', 'hora_inicial', 'hora_final', 'tempo_investido_minutos', 'observacao']
        widgets = {
            'data': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'hora_inicial': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'hora_final': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'tempo_investido_minutos': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'autocomplete': 'off'}),
            'observacao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class AtividadeForm(forms.ModelForm):
    class Meta:
        model = Atividade
        fields = ['nome', 'ativo', 'ordem']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ordem': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class PrioridadeForm(forms.ModelForm):
    class Meta:
        model = Prioridade
        fields = ['nome', 'ativo', 'ordem', 'cor']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input form-switch'}),
            'ordem': forms.NumberInput(attrs={'class': 'form-control'}),
            'cor': forms.TextInput(attrs={'class': 'form-control form-control-color', 'type': 'color', 'title': 'Escolha a cor'}),
        }


class TipoProblemaForm(forms.ModelForm):
    class Meta:
        model = TipoProblema
        fields = ['nome', 'ativo', 'ordem']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input form-switch'}),
            'ordem': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class EquipeForm(forms.ModelForm):
    class Meta:
        model = Equipe
        fields = ['nome', 'ativo', 'ordem']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input form-switch'}),
            'ordem': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class ProjetoForm(forms.ModelForm):
    class Meta:
        model = Projeto
        fields = ['nome', 'ativo']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SolicitanteForm(forms.ModelForm):
    class Meta:
        model = Solicitante
        fields = ['nome', 'ativo']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TipoProblemaForm(forms.ModelForm):
    class Meta:
        model = TipoProblema
        fields = ['nome', 'ativo', 'ordem']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ordem': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class EquipeForm(forms.ModelForm):
    class Meta:
        model = Equipe
        fields = ['nome', 'ativo', 'ordem']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ordem': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class ProjetoForm(forms.ModelForm):
    class Meta:
        model = Projeto
        fields = ['nome', 'ativo', 'ordem']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input form-switch'}),
            'ordem': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class SolicitanteForm(forms.ModelForm):
    class Meta:
        model = Solicitante
        fields = ['nome', 'ativo', 'ordem']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input form-switch'}),
            'ordem': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class PrioridadeForm(forms.ModelForm):
    class Meta:
        model = Prioridade
        fields = ['nome', 'ativo', 'ordem', 'cor']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input form-switch'}),
            'ordem': forms.NumberInput(attrs={'class': 'form-control'}),
            'cor': forms.TextInput(attrs={'class': 'form-control form-control-color', 'type': 'color', 'title': 'Escolha a cor'}),
        }


class AtividadeForm(forms.ModelForm):
    class Meta:
        model = Atividade
        fields = ['nome', 'ativo', 'ordem']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input form-switch'}),
            'ordem': forms.NumberInput(attrs={'class': 'form-control'}),
        }
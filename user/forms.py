from django import forms
from django.contrib.auth.models import User
from django.contrib.auth import password_validation as password_validation
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from .models import Cliente, Equipamento, PerfilUsuario, Time, Apontamento
import csv
import openpyxl
from datetime import date, timedelta, time
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

User = get_user_model()


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['corporation_id', 'corporation', 'plant_id', 'plant',
                  'unat', 'city', 'state_province', 'country', 'region',
                  'business', 'zone', 'ativo']
        widgets = {
            'corporation_id': forms.TextInput(attrs={'class': 'form-control'}),
            'corporation': forms.TextInput(attrs={'class': 'form-control'}),
            'plant_id': forms.TextInput(attrs={'class': 'form-control'}),
            'plant': forms.TextInput(attrs={'class': 'form-control'}),
            'unat': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state_province': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'region': forms.TextInput(attrs={'class': 'form-control'}),
            'business': forms.TextInput(attrs={'class': 'form-control'}),
            'zone': forms.TextInput(attrs={'class': 'form-control'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'corporation_id': 'ID Corporação',
            'corporation': 'Corporação',
            'plant_id': 'ID Planta',
            'plant': 'Planta',
            'unat': 'UNAT',
            'city': 'Cidade',
            'state_province': 'Estado/Província',
            'country': 'País',
            'region': 'Região',
            'business': 'Negócio',
            'zone': 'Zona',
        }

    def clean(self):
        cleaned_data = super().clean()
        corp_id = cleaned_data.get('corporation_id')
        plant_id = cleaned_data.get('plant_id')
        if corp_id and plant_id:
            qs = Cliente.objects.filter(corporation_id=corp_id, plant_id=plant_id)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError('Já existe um cliente com este ID Corporação e ID Planta.')
        return cleaned_data


class ClienteImportForm(forms.Form):
    arquivo = forms.FileField(
        label='Arquivo Excel (.xlsx) ou CSV (.csv)',
        help_text='Colunas esperadas: CORPORATION_ID, CORPORATION, PLANT_ID, PLANT, UNAT, CITY, STATE_PROVINCE, COUNTRY, REGION, BUSINESS, ZONE',
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.xlsx,.xls,.csv'})
    )
    atualizar_existentes = forms.BooleanField(
        label='Atualizar clientes existentes',
        required=False,
        initial=True,
        help_text='Se marcado, atualiza clientes com mesmo corporation_id + plant_id. Se desmarcado, pula duplicados.',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def clean_arquivo(self):
        arquivo = self.cleaned_data.get('arquivo')
        if not arquivo:
            raise forms.ValidationError('Selecione um arquivo para importar.')
        ext = arquivo.name.lower().split('.')[-1]
        if ext not in ['xlsx', 'xls', 'csv']:
            raise forms.ValidationError('Formato não suportado. Use .xlsx, .xls ou .csv')
        return arquivo


class UsuarioForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(label='Nome', required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(label='Sobrenome', required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    role = forms.ChoiceField(
        label='Função',
        choices=PerfilUsuario.ROLE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    time = forms.ModelChoiceField(
        label='Time/Equipe',
        queryset=None,
        required=False,
        empty_label='Sem equipe',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    telefone = forms.CharField(
        label='Telefone',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    is_active = forms.BooleanField(
        label='Ativo',
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'password1': forms.PasswordInput(attrs={'class': 'form-control'}),
            'password2': forms.PasswordInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Time
        self.fields['time'].queryset = Time.objects.filter(ativo=True)
        # Reorder fields to put password2 right after password1
        field_order = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2', 'role', 'time', 'telefone', 'is_active']
        self.order_fields(field_order)
        # Aplicar validações padrão de senha e reduzir help text
        password = self.fields['password1']
        password.help_text = 'Mínimo de 8 caracteres, com letras e números.'
        self.fields['password2'].help_text = 'Repita a senha para confirmação.'
        # Garantir que os inputs de senha tenham a mesma classe dos demais (form-control)
        for field_name in ['password1', 'password2']:
            widget = self.fields[field_name].widget
            existing = widget.attrs.get('class', '')
            widget.attrs['class'] = (existing + ' form-control').strip()

    def clean_password2(self):
        from django.contrib.auth import password_validation as pv
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('As senhas não coincidem.')
        if password2:
            pv.validate_password(password2, user=self.instance)
            # Regra extra: não igual ao username
            username = self.data.get('username', '') or (self.instance.username if self.instance else '')
            if username and password2 == username:
                raise forms.ValidationError('A senha não pode ser igual ao nome de usuário.')
        return password2

    def _validate_password_for_user(self, value):
        username = self.data.get('username', '') or (self.instance.username if self.instance else '')
        if username and value == username:
            raise forms.ValidationError('A senha não pode ser igual ao nome de usuário.')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.is_active = self.cleaned_data['is_active']
        if commit:
            user.save()
            PerfilUsuario.objects.update_or_create(
                user=user,
                defaults={
                    'role': self.cleaned_data['role'],
                    'time': self.cleaned_data['time'],
                    'telefone': self.cleaned_data['telefone'],
                    'ativo': self.cleaned_data['is_active'],
                }
            )
        return user


class ApontamentoForm(forms.ModelForm):
    """Formulário de Apontamento com seleção de Corporação e Planta separadas.
    O campo 'cliente' (FK) é preenchido automaticamente baseado na combinação
    corporacao_id + plant_id selecionados."""
    
    corporacao = forms.CharField(
        label='Corporação',
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_corporacao',
            'placeholder': 'Digite para buscar corporação...',
            'autocomplete': 'off',
        })
    )
    corporacao_id = forms.CharField(
        widget=forms.HiddenInput(attrs={'id': 'id_corporacao_id'}),
        required=False
    )
    planta = forms.CharField(
        label='Planta/Unidade',
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_planta',
            'placeholder': 'Selecione uma corporação primeiro...',
            'autocomplete': 'off',
            'disabled': 'disabled',
        })
    )
    planta_id = forms.CharField(
        widget=forms.HiddenInput(attrs={'id': 'id_planta_id'}),
        required=False
    )

    class Meta:
        model = Apontamento
        fields = [
            'corporacao', 'corporacao_id', 'planta', 'planta_id',
            'projeto', 'solicitante', 'ticket', 'equipamento',
            'prioridade', 'equipe', 'responsavel', 'atividade', 'tipo_problema',
            'status', 'data', 'hora_inicial', 'hora_final',
            'gw_ar', 'desvio', 'descricao'
        ]
        widgets = {
            'projeto': forms.TextInput(attrs={'class': 'form-control'}),
            'solicitante': forms.TextInput(attrs={'class': 'form-control'}),
            'ticket': forms.TextInput(attrs={'class': 'form-control'}),
            'equipamento': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_equipamento',
                'disabled': 'disabled',
            }),
            'prioridade': forms.Select(attrs={'class': 'form-select'}),
            'equipe': forms.Select(attrs={'class': 'form-select'}),
            'responsavel': forms.Select(attrs={'class': 'form-select'}),
            'atividade': forms.Select(attrs={'class': 'form-select'}),
            'tipo_problema': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'data': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'hora_inicial': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'hora_final': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'gw_ar': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'desvio': forms.Select(attrs={'class': 'form-select'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Guarda o usuário para uso no clean()
        self._user = user
        
        # Filtrar responsáveis baseado nas permissões do usuário
        if user:
            perfil = user.perfil if hasattr(user, 'perfil') else None
            if perfil and perfil.is_gestor_or_above():
                responsavel_qs = User.objects.filter(
                    perfil__ativo=True, is_active=True
                ).select_related('perfil').order_by('first_name', 'last_name')
                self.fields['responsavel'].widget = forms.Select(attrs={'class': 'form-select'})
            elif perfil and perfil.is_lider_or_above():
                responsavel_qs = User.objects.filter(
                    perfil__ativo=True, is_active=True, perfil__time=perfil.time
                ).select_related('perfil').order_by('first_name', 'last_name')
                self.fields['responsavel'].widget = forms.Select(attrs={'class': 'form-select'})
            else:
                responsavel_qs = User.objects.filter(id=user.id)
                self.fields['responsavel'].widget = forms.HiddenInput()
                self.fields['responsavel'].initial = user.id
        else:
            responsavel_qs = User.objects.none()
            self.fields['responsavel'].widget = forms.HiddenInput()
        
        self.fields['responsavel'].queryset = responsavel_qs
        
        # Equipamento: queryset vazio inicialmente (será preenchido via JS após selecionar planta)
        self.fields['equipamento'].queryset = Equipamento.objects.none()
        self.fields['equipamento'].empty_label = "Selecione uma planta primeiro"
        
        # Pré-preencher corporação/planta se estiver editando
        if self.instance.pk and self.instance.cliente_id:
            cliente = self.instance.cliente
            self.fields['corporacao'].initial = cliente.corporation
            self.fields['corporacao_id'].initial = cliente.corporation_id
            self.fields['planta'].initial = cliente.plant
            self.fields['planta_id'].initial = cliente.plant_id
            # Habilita planta e equipamento na edição
            self.fields['planta'].widget.attrs.pop('disabled', None)
            self.fields['planta'].widget.attrs['placeholder'] = 'Digite para buscar planta...'
            self.fields['equipamento'].widget.attrs.pop('disabled', None)
            # Pré-carregar equipamentos da planta
            self.fields['equipamento'].queryset = Equipamento.objects.filter(
                cliente=cliente, ativo=True
            ).select_related('cliente').order_by('numero_serie')
            self.fields['equipamento'].empty_label = "Nenhum"
        
        # Remover opção vazia dos selects obrigatórios
        for field_name in ['equipe', 'prioridade', 'atividade', 'tipo_problema', 'status', 'desvio']:
            field = self.fields[field_name]
            field.empty_label = None
            widget = field.widget
            if hasattr(widget, 'choices'):
                choices = list(widget.choices)
                widget.choices = [(v, l) for v, l in choices if v not in (None, '')]
        
        if not self.instance.pk:
            self.fields['data'].initial = date.today()
        
        # Bloquear seleção de datas futuras no datepicker
        self.fields['data'].widget.attrs['max'] = date.today().isoformat()
        
        # Filtrar equipes: admin/gestor escolhem qualquer (PMC/SHD);
        # líder/colaborador ficam restritos à equipe do próprio perfil
        equipe_choices = [c for c in self.fields['equipe'].choices if c[0] in ['pmc', 'shd']]
        if user:
            perfil = getattr(user, 'perfil', None)
            if perfil and not perfil.is_gestor_or_above():
                time_nome = perfil.time.nome.lower() if perfil.time else ''
                equipe_codigo = time_nome
                equipe_choices = [c for c in equipe_choices if c[0] == equipe_codigo]
                if not equipe_choices and perfil.time:
                    equipe_choices = [(equipe_codigo, perfil.time.nome.upper())]
        self.fields['equipe'].choices = equipe_choices
        
        # Responsável: para gestor/líder é um select visível -> sem opção vazia
        if not isinstance(self.fields['responsavel'].widget, forms.HiddenInput):
            self.fields['responsavel'].empty_label = None

    def clean(self):
        cleaned_data = super().clean()
        corporacao_id = cleaned_data.get('corporacao_id')
        planta_id = cleaned_data.get('planta_id')
        hora_inicial = cleaned_data.get('hora_inicial')
        hora_final = cleaned_data.get('hora_final')
        data = cleaned_data.get('data')
        data_fim = cleaned_data.get('data_fim')
        responsavel = cleaned_data.get('responsavel')
        
        # Validar se corporação e planta foram selecionadas
        if not corporacao_id or not planta_id:
            raise forms.ValidationError(
                'Selecione uma Corporação e uma Planta válidas.'
            )
        
        # Buscar o cliente correspondente
        try:
            cliente = Cliente.objects.get(
                corporation_id=corporacao_id,
                plant_id=planta_id,
                ativo=True
            )
            cleaned_data['cliente'] = cliente
        except Cliente.DoesNotExist:
            raise forms.ValidationError(
                'A combinação de Corporação e Planta selecionada não existe ou está inativa.'
            )
        except Cliente.MultipleObjectsReturned:
            raise forms.ValidationError(
                'Erro: múltiplos clientes encontrados para esta Corporação/Planta. Contate o administrador.'
            )
        
        # Get user for role-based restrictions
        user = getattr(self, '_user', None)
        perfil = user.perfil if user and hasattr(user, 'perfil') else None
        
        if hora_inicial and hora_final:
            if hora_final <= hora_inicial:
                raise forms.ValidationError(
                    'Horário final deve ser posterior ao horário inicial. '
                    'Apontamentos não podem ultrapassar meia-noite.'
                )
            if hora_final > time(23, 59):
                raise forms.ValidationError('Horário final não pode ultrapassar 23:59.')
        
        if data:
            if data > date.today():
                raise forms.ValidationError('Data de início não pode ser no futuro. Apenas hoje ou dias anteriores.')
        
        if data_fim and data and data_fim < data:
            raise forms.ValidationError('Data de fim não pode ser anterior à data de início.')
        
        if data_fim and data and data_fim == data:
            if hora_inicial and hora_final and hora_final <= hora_inicial:
                raise forms.ValidationError('Hora final deve ser posterior à hora inicial no mesmo dia.')
        
        if data and responsavel:
            qs = Apontamento.objects.filter(
                responsavel=responsavel,
                data=data
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            
            for ap in qs:
                if (hora_inicial < ap.hora_final and hora_final > ap.hora_inicial):
                    raise forms.ValidationError(
                        f'Conflito de horário: {responsavel.get_full_name()} já tem apontamento '
                        f"({ap.hora_inicial}-{ap.hora_final}) neste dia."
                    )
        
        return cleaned_data

    def save(self, commit=True):
        # O cliente foi validado no clean() e está em cleaned_data
        # Precisamos atribuir à instância antes de salvar
        if 'cliente' in self.cleaned_data:
            self.instance.cliente = self.cleaned_data['cliente']
        # Definir criado_por se não estiver definido (criação)
        if not self.instance.pk and hasattr(self, '_user') and self._user:
            self.instance.criado_por = self._user
        return super().save(commit=commit)


class UsuarioUpdateForm(UserChangeForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(label='Nome', required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(label='Sobrenome', required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    role = forms.ChoiceField(
        label='Função',
        choices=PerfilUsuario.ROLE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    time = forms.ModelChoiceField(
        label='Time/Equipe',
        queryset=None,
        required=False,
        empty_label='Sem equipe',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    telefone = forms.CharField(
        label='Telefone',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    is_active = forms.BooleanField(
        label='Ativo',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    # Password fields (only for admin)
    password1 = forms.CharField(
        label='Nova Senha',
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
        help_text='Deixe em branco para não alterar a senha.'
    )
    password2 = forms.CharField(
        label='Confirmar Nova Senha',
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
        help_text='Digite a mesma senha novamente para confirmação.'
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'is_active')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)
        self.fields.pop('password', None)
        from .models import Time
        self.fields['time'].queryset = Time.objects.filter(ativo=True)
        if self.instance and hasattr(self.instance, 'perfil'):
            self.fields['role'].initial = self.instance.perfil.role
            self.fields['time'].initial = self.instance.perfil.time
            self.fields['telefone'].initial = self.instance.perfil.telefone
            self.fields['is_active'].initial = self.instance.perfil.ativo
        
        # Remove password fields if not admin
        if not (self.request_user and (self.request_user.is_superuser or 
             hasattr(self.request_user, 'perfil') and self.request_user.perfil.is_admin())):
            self.fields.pop('password1', None)
            self.fields.pop('password2', None)

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 or password2:
            if password1 != password2:
                raise forms.ValidationError('As senhas não coincidem.')
            if len(password1) < 8:
                raise forms.ValidationError('A senha deve ter pelo menos 8 caracteres.')
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.is_active = self.cleaned_data['is_active']
        password1 = self.cleaned_data.get('password1')
        if password1:
            user.set_password(password1)
        if commit:
            user.save()
            PerfilUsuario.objects.update_or_create(
                user=user,
                defaults={
                    'role': self.cleaned_data['role'],
                    'time': self.cleaned_data['time'],
                    'telefone': self.cleaned_data['telefone'],
                    'ativo': self.cleaned_data['is_active'],
                }
            )
        return user


class PublicRegistrationForm(UserCreationForm):
    """Formulário de cadastro público - apenas emails @semeq.com"""
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'seu.email@semeq.com'})
    )
    first_name = forms.CharField(
        label='Nome', required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Seu nome'})
    )
    last_name = forms.CharField(
        label='Sobrenome', required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Seu sobrenome'})
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'usuario'}),
            'password1': forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Senha', 'autocomplete': 'new-password'}),
            'password2': forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirmar senha', 'autocomplete': 'new-password'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ajustar help texts
        self.fields['password1'].help_text = 'Mínimo 8 caracteres, com letras e números.'
        self.fields['password2'].help_text = 'Repita a senha para confirmação.'
        # Reorder fields
        field_order = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']
        self.order_fields(field_order)

    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower()
        if not email.endswith('@semeq.com'):
            raise forms.ValidationError('Apenas emails @semeq.com são permitidos no momento.')
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Este email já está cadastrado.')
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username', '').lower()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('Este nome de usuário já está em uso.')
        return username

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('As senhas não coincidem.')
        if password2:
            from django.contrib.auth import password_validation as pv
            pv.validate_password(password2, user=self.instance)
            username = self.cleaned_data.get('username', '')
            if username and password2 == username:
                raise forms.ValidationError('A senha não pode ser igual ao nome de usuário.')
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.is_active = True  # Ativo por padrão
        if commit:
            user.save()
            # Criar perfil padrão (colaborador, sem time)
            PerfilUsuario.objects.create(
                user=user,
                role='usuario',
                time=None,
                ativo=True,
                telefone=''
            )
        return user


class SemeqPasswordResetForm(PasswordResetForm):
    """Password reset apenas para emails @semeq.com"""
    
    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower()
        if not email.endswith('@semeq.com'):
            raise forms.ValidationError('Apenas emails @semeq.com são permitidos.')
        # Verifica se existe usuário ativo com este email
        users = User.objects.filter(email__iexact=email, is_active=True)
        if not users.exists():
            # Não revelar se email existe ou não (segurança)
            # Mas para UX, podemos deixar passar e o Django trata no send_mail
            pass
        return email
import os, sys
os.environ['DJANGO_ALLOWED_HOSTS'] = 'localhost,127.0.0.1,testserver'
os.environ['DJANGO_SETTINGS_MODULE'] = 'apontamento.settings'
sys.path.insert(0, r'C:\Users\crist\OneDrive\Documentos\Work\apontamento-semeq\apontamento-semeq')
import django; django.setup()
from django.contrib.auth import get_user_model
from user.models import Cliente, Equipamento, Apontamento
from datetime import date

User = get_user_model()

def get_or_create_cliente(corp_id, corporation, plant_id, plant, city, country):
    obj, created = Cliente.objects.get_or_create(
        corporation_id=corp_id,
        plant_id=plant_id,
        defaults={
            'corporation': corporation,
            'plant': plant,
            'city': city,
            'country': country,
            'ativo': True,
        }
    )
    return obj

print('=== Clientes ===')
clientes = [
    ('AB-INBEV', 'AB INBEV', 'ACC', 'Accra Plant', 'Accra', 'Ghana'),
    ('CBC', 'CBC', 'BRA', 'Brasil', 'Sao Paulo', 'Brasil'),
    ('DIGITEL', 'Digitel', 'VEN', 'Venezuela', 'Caracas', 'Venezuela'),
    ('NAMIBREW', 'Namibrew', 'WIND', 'Windhoek', 'Windhoek', 'Namibia'),
    ('SOLAR', 'Solar', 'SLZ', 'Sao Luis', 'Sao Luis', 'Brasil'),
]
created_clients = []
for c in clientes:
    cli = get_or_create_cliente(*c)
    created_clients.append(cli)
    print('  -', cli.corporation, cli.plant)

print('=== Equipamentos ===')
equipamentos = [
    ('Gateway', 'GW-1001', 'Modelo GW-100', created_clients[0]),
    ('Bomba', 'BM-2001', 'Modelo BM-X', created_clients[1]),
    ('Sensor', 'SN-3001', 'Sensor T', created_clients[2]),
    ('Controlador', 'CT-4001', 'Control C1', created_clients[3]),
    ('Gateway', 'GW-2002', 'Modelo GW-200', created_clients[4]),
]
created_equip = []
for tipo, serie, modelo, cli in equipamentos:
    eq, created = Equipamento.objects.get_or_create(
        numero_serie=serie,
        defaults={'tipo': tipo, 'modelo': modelo, 'cliente': cli, 'ativo': True}
    )
    created_equip.append(eq)
    print('  -', eq.numero_serie)

print('=== Apontamentos ===')
colab1 = User.objects.get(username='colab_pmc1')
colab2 = User.objects.get(username='colab_pmc2')
admin = User.objects.get(username='admin')

apontamentos = [
    # cli, equip, ticket, responsavel, data, inicio, fim, status
    (created_clients[0], created_equip[0], 'TKT-1001', colab1, date.today(), '08:00', '08:35', 'concluido'),
    (created_clients[0], created_equip[0], 'TKT-1002', colab1, date.today(), '08:40', '09:25', 'andamento'),
    (created_clients[1], created_equip[1], 'TKT-1003', colab2, date.today(), '09:30', '10:10', 'aberto'),
    (created_clients[2], created_equip[2], 'TKT-1004', colab1, date.today(), '10:15', '10:45', 'aberto'),
    (created_clients[3], created_equip[3], 'TKT-1005', colab2, date.today(), '11:00', '12:00', 'concluido'),
    (created_clients[4], created_equip[4], 'TKT-1006', admin, date.today(), '10:00', '11:00', 'andamento'),
]

def parse_hora(s):
    h, m = s.split(':')
    from datetime import time as t
    return t(int(h), int(m))

for cli, eq, ticket, resp, data, hi, hf, status in apontamentos:
    if Apontamento.objects.filter(ticket=ticket).exists():
        continue
    ap = Apontamento(
        cliente=cli, equipamento=eq, projeto='Projeto ' + cli.corporation,
        solicitante='Solicitante', ticket=ticket, prioridade='media',
        equipe=resp.perfil.time.nome.lower() if resp.perfil and resp.perfil.time else 'pmc',
        responsavel=resp, atividade='suporte', tipo_problema='software',
        status=status, data=data, hora_inicial=parse_hora(hi), hora_final=parse_hora(hf),
        gw_ar=True, desvio='nenhum', descricao='Apontamento de exemplo ' + ticket,
        criado_por=resp,
    )
    ap.save()
    print('  -', ticket, resp.username, hi, '-', hf)

print()
print('=== RESUMO ===')
print('Clientes:', Cliente.objects.count())
print('Equipamentos:', Equipamento.objects.count())
print('Apontamentos:', Apontamento.objects.count())

import boto3
import os
import time
from dotenv import load_dotenv
from functions import configura_instancia, cria_instancia, cria_scaling,  deleta_scaling

load_dotenv()

ACCESS_KEY = os.getenv("ACCESS_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")


# ----------- POSTGRES INFO-------------
region_Ohio = 'us-east-2'
Kp_Ohio = 'KEY_OHIO'
sg_ohio = 'ohio-bia'
image_ohio = 'ami-020db2c14939a8efb'
tag_ohio = 'postgres-bia'
user_data_ohio = '''#!/bin/bash
cd /
sudo apt update
sudo apt install postgresql postgresql-contrib -y
sudo -u postgres createuser cloud
sudo -u postgres createdb tasks -O cloud
sudo sed -i s/"^#listen_addresses = 'localhost'"/"listen_addresses = '*'"/g  /etc/postgresql/10/main/postgresql.conf
sudo sed -i '$a host all all 0.0.0.0/0 trust' /etc/postgresql/10/main/pg_hba.conf
sudo ufw allow 5432/tcp
sudo systemctl restart postgresql
'''


# ----------- DJANGO INFO-------------
region_Nv = 'us-east-1'
Kp_Nv = 'KEY_NV'
sg_nv = 'nv-bia'
lb_nv = 'lb-bia'
image_nv = 'ami-0279c3b3186e54acd'
tag_nv = 'django-bia'
tg_nv = 'BiaTargetGroup'
image_tag = 'bia-NV'
launch_config_nv = 'launch_config_bia'
asg_nv = 'asg_bia'
policy_name_nv = 'biaNV-target-tracking-scaling-policy'


deleta_scaling(ACCESS_KEY, SECRET_KEY, lb_nv, tg_nv, launch_config_nv, asg_nv)

ec2_ohio = boto3.client('ec2', aws_access_key_id=ACCESS_KEY,
                        aws_secret_access_key=SECRET_KEY, region_name=region_Ohio)

vpc_list_ohio = ec2_ohio.describe_vpcs()
vpc_ohio = vpc_list_ohio['Vpcs'][0]['VpcId']

sc_ohio_id = configura_instancia(region_Ohio, Kp_Ohio, sg_ohio,
                                 vpc_ohio, ACCESS_KEY, SECRET_KEY)
ohio_id = cria_instancia(region_Ohio, user_data_ohio,
                         image_ohio, Kp_Ohio, sg_ohio, tag_ohio)


response = ec2_ohio.describe_instances(
    InstanceIds=[ohio_id])

ohio_ip = response['Reservations'][0]['Instances'][0]['NetworkInterfaces'][0]['Association']['PublicIp']


user_data_nv = '''#!/bin/bash
cd /
sudo apt update
git clone https://github.com/raulikeda/tasks.git
cd tasks
sudo sed -i s/"'HOST': 'node1',"/"'HOST': '{0}',"/g  portfolio/settings.py
sudo sed -i s/"'PASSWORD': 'cloud',"/"'PASSWORD': '',"/g  portfolio/settings.py
./install.sh
sudo ufw allow 8080/tcp
./run.sh
'''.format(ohio_ip)


ec2_nv = boto3.client('ec2', aws_access_key_id=ACCESS_KEY,
                      aws_secret_access_key=SECRET_KEY, region_name=region_Nv)

ec2_nv_res = boto3.resource('ec2', region_name='us-east-1')

vpc_list_nv = ec2_nv.describe_vpcs()
vpc_nv = vpc_list_nv['Vpcs'][0]['VpcId']

sc_nv_id = configura_instancia(
    region_Nv, Kp_Nv, sg_nv, vpc_nv, ACCESS_KEY, SECRET_KEY)
nv_id = cria_instancia(region_Nv, user_data_nv,
                       image_nv, Kp_Nv, sg_nv, tag_nv)


get_image = ec2_nv.describe_images(
    Owners=['self'],
    Filters=[{
        'Name': 'name',
        'Values': [image_tag]}, ],
)
if len(get_image['Images']):
    print('Apagando Imagem não utilizada')
    image_id = get_image['Images'][0]['ImageId']
    image = list(ec2_nv_res.images.filter(ImageIds=[image_id]).all())[0]
    image.deregister()
    print('Imagem apagada com sucesso')

print('Criando nova imagem')
image_id = ec2_nv.create_image(InstanceId=nv_id, Name=image_tag)
print('Imagem criada com sucesso')
print('ID da Imagem: ', image_id['ImageId'])


image = ec2_nv_res.Image(image_id['ImageId'])
if(image.state == 'pending'):
    print("Esperando a imagem ficar disponível")
    while(image.state != 'available'):
        image = ec2_nv_res.Image(image_id['ImageId'])
    print("Imagem pronta para uso")


print('Encerrando instância do Django')
encerrar_instancia = ec2_nv.terminate_instances(
    InstanceIds=[
        nv_id,
    ],
)
print('Instância encerrada')


cria_scaling(ACCESS_KEY, SECRET_KEY, ec2_nv, lb_nv, sc_nv_id, vpc_nv,
             user_data_nv, launch_config_nv, Kp_Nv, asg_nv, policy_name_nv, tag_nv, tg_nv)


print("Script Concluído")

import boto3
import logging


def configura_instancia(region_name, key_name, SecGroup_name, vpc_id, ACCESS_KEY, SECRET_KEY):

    try:
        # configure which region to use
        ec2 = boto3.client('ec2', aws_access_key_id=ACCESS_KEY,
                           aws_secret_access_key=SECRET_KEY, region_name=region_name)

        # delete keypair if already exists and create a new one with de same name

        print('Criando Key pair para {0}'.format(region_name))
        logging.info('Criando Key pair para {0}'.format(region_name))

        delete_kp = ec2.delete_key_pair(KeyName=key_name)
        key_pair = ec2.create_key_pair(KeyName=key_name)

        file = open('{0}.pem'.format(key_name), 'w')
        file.write(key_pair['KeyMaterial'])
        file.close()

        print('Key pair criada com sucesso!')
        logging.info('Key pair criada com sucesso!')

        waiter = ec2.get_waiter('instance_terminated')
        inst_desc = ec2.describe_instances()

        instances_id = []
        for res in inst_desc['Reservations']:
            for inst in res['Instances']:
                for sec_group in inst['SecurityGroups']:
                    if SecGroup_name in sec_group.values():
                        instances_id.append(inst['InstanceId'])

        if len(instances_id) != 0:
            print('Apagando Instâncias não utilizadas')
            logging.info('Apagando Instâncias não utilizadas')

            encerrar_instancia = ec2.terminate_instances(
                InstanceIds=instances_id,
            )
            waiter.wait(

                InstanceIds=instances_id,
                WaiterConfig={
                    'Delay': 10,
                    'MaxAttempts': 123
                }
            )
            print('Deletas com sucesso')
            logging.info('Deletas com sucesso')

        # delete security group if already exists and create a new one with de same name
        print('Criando Security Group para {0}'.format(region_name))
        logging.info('Criando Security Group para {0}'.format(region_name))

        response = ec2.describe_security_groups(
            Filters=[
                dict(Name='group-name', Values=[SecGroup_name])
            ]
        )
        if response['SecurityGroups']:
            group_id = response['SecurityGroups'][0]['GroupId']
            delete_sc = ec2.delete_security_group(
                GroupId=group_id,
            )

        security_group = ec2.create_security_group(
            GroupName=SecGroup_name,
            Description='projeto final',
            VpcId=vpc_id,
        )

        print('Liberando portas de acesso')
        logging.info('Liberando portas de acesso')

        ec2.authorize_security_group_ingress(
            GroupId=security_group['GroupId'],
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 80,
                    'ToPort': 80,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                },
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 22,
                    'ToPort': 22,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                }


            ]
        )

        if region_name == 'us-east-2':
            ec2.authorize_security_group_ingress(
                GroupId=security_group['GroupId'],
                IpPermissions=[
                    {
                        'IpProtocol': 'tcp',
                        'FromPort': 5432,
                        'ToPort': 5432,
                        'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                    }
                ]
            )
        else:

            ec2.authorize_security_group_ingress(
                GroupId=security_group['GroupId'],
                IpPermissions=[
                    {
                        'IpProtocol': 'tcp',
                        'FromPort': 8080,
                        'ToPort': 8080,
                        'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                    }
                ]
            )

        print('Security Group criado com sucesso')
        logging.info('Security Group criado com sucesso')

        print('Configuração feita com sucesso')
        logging.info('Configuração feita com sucesso')

        print("KeyPair and Security group created")
        logging.info("KeyPair and Security group created")

        return security_group['GroupId']

    except Exception as e:
        print(e)
        logging.error('Erro durante a configuração')


def cria_instancia(region_name, user_data, image_id, key_name, SecGroup_name, tag):
    try:
        print('Criando instância para {0}'.format(region_name))
        logging.info('Criando instância para {0}'.format(region_name))

        ec2_instancia = boto3.resource('ec2', region_name=region_name)
        instancia = ec2_instancia.create_instances(
            ImageId=image_id,
            MinCount=1,
            MaxCount=1,
            InstanceType='t2.micro',
            KeyName=key_name,
            BlockDeviceMappings=[
                {
                    'DeviceName': "/dev/xvda",
                    'Ebs': {
                        'DeleteOnTermination': True,
                        'VolumeSize': 8
                    }
                }
            ],
            SecurityGroups=[SecGroup_name],
            UserData=user_data
        )

        print('Adicionando Tags')
        logging.info('Adicionando Tags')

        id_instancia = instancia[0].instance_id

        ec2_instancia.create_tags(
            Resources=[id_instancia], Tags=[{'Key': 'Name', 'Value': tag}])

        instancia[0].wait_until_running()
        print('Instância criada com sucesso! ')
        logging.info('Instância criada com sucesso! ')
        return id_instancia
    except Exception as e:
        print(e)
        logging.error('Erro ao criar a instância ')


def cria_scaling(ACCESS_KEY, SECRET_KEY, ec2_nv, lb_nv, sc_nv_id, vpc_id, user_data_nv, launch_config_nv, Kp_Nv, asg_nv, policy_name_nv, tag_nv, tg_nv):

    try:

        elb_client = boto3.client(service_name="elbv2", region_name="us-east-1",
                                  aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY)

        ec2_autoscaling = boto3.client(service_name='autoscaling',  region_name="us-east-1",
                                       aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY)

        subnet_list = ec2_nv.describe_subnets()

        subnets = []
        for sn in subnet_list['Subnets']:
            subnets.append(sn['SubnetId'])

        create_lb_response = elb_client.create_load_balancer(Name=lb_nv,
                                                             Subnets=subnets,
                                                             SecurityGroups=[
                                                                 sc_nv_id],
                                                             Scheme='internet-facing')

        lbId = create_lb_response['LoadBalancers'][0]['LoadBalancerArn']
        print('Load Balancer criado com sucesso')
        logging.info('Load Balancer criado com sucesso')

        print('Criando grupos de Destino')
        logging.info('Criando grupos de Destino')

        create_tg = elb_client.create_target_group(Name=tg_nv,
                                                   Protocol='HTTP',
                                                   Port=8080,
                                                   VpcId=vpc_id)

        tgId = create_tg['TargetGroups'][0]['TargetGroupArn']

        print('Criando Listener')
        logging.info('Criando Listener')

        create_listener_response = elb_client.create_listener(LoadBalancerArn=lbId,
                                                              Protocol='HTTP', Port=80,
                                                              DefaultActions=[{'Type': 'forward',
                                                                               'TargetGroupArn': tgId}])

        get_image_id = ec2_nv.describe_images(Owners=['self'])
        imageId = get_image_id['Images'][0]['ImageId']

        print('Criando Launch Configuration')
        logging.info('Criando Launch Configuration')

        launch_config = ec2_autoscaling.create_launch_configuration(
            LaunchConfigurationName=launch_config_nv,
            ImageId=imageId,
            KeyName=Kp_Nv,
            UserData=user_data_nv,
            SecurityGroups=[sc_nv_id],
            InstanceType='t2.micro'
        )

        print('Criando Autoscaling')
        logging.info('Criando Autoscaling')

        auto_scaling_Nv = ec2_autoscaling.create_auto_scaling_group(
            AutoScalingGroupName=asg_nv,
            LaunchConfigurationName=launch_config_nv,
            TargetGroupARNs=[tgId],
            MaxInstanceLifetime=2592000,
            MaxSize=3,
            MinSize=1,
            VPCZoneIdentifier=subnets[4],
            Tags=[
                {
                    "Key": "Name",
                    "Value": tag_nv,
                    "PropagateAtLaunch": True
                }
            ]
        )

        cmd_res_label = 'a' + lbId.split('/a')[1] + '/t' + tgId.split(':t')[1]

        response = ec2_autoscaling.put_scaling_policy(
            AutoScalingGroupName=asg_nv,
            PolicyName=policy_name_nv,
            PolicyType='TargetTrackingScaling',
            TargetTrackingConfiguration={
                'PredefinedMetricSpecification': {
                    'PredefinedMetricType': 'ALBRequestCountPerTarget',
                    'ResourceLabel': cmd_res_label,
                },
                'TargetValue': 50.0,
            },
        )

        print('Autoscaling criado com sucesso')
        logging.info('Autoscaling criado com sucesso')

    except Exception as e:
        print(e)
        logging.error('Erro ao criar Scaling')

    return "Escalabilidade realizada com sucesso!"


def deleta_scaling(ACCESS_KEY, SECRET_KEY, lb_nv, tg_nv, launch_config_nv, asg_nv):

    elb_client = boto3.client(service_name="elbv2", region_name="us-east-1",
                              aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY)
    ec2_autoscaling = boto3.client(service_name='autoscaling',  region_name="us-east-1",
                                   aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY)

    print('Deletando dependências')
    logging.info('Deletando dependências')

    load_balancers = elb_client.describe_load_balancers()

    for i in load_balancers['LoadBalancers']:
        if i['LoadBalancerName'] == lb_nv:
            lb_id = i['LoadBalancerArn']

            listeners = elb_client.describe_listeners(LoadBalancerArn=lb_id)

            if listeners['Listeners']:
                listener_arn = listeners['Listeners'][0]['ListenerArn']
                print('Deletando Listener')
                logging.info('Deletando Listener')

                elb_client.delete_listener(ListenerArn=listener_arn)
                print('Deletando Load Balancer')
                logging.info('Deletando Load Balancer')

            elb_client.delete_load_balancer(LoadBalancerArn=lb_id)

    try:
        tg = elb_client.describe_target_groups(
            Names=[
                tg_nv,
            ],
        )

        tg_arn = tg['TargetGroups'][0]['TargetGroupArn']

        print('Deletando Target Group')
        logging.info('Deletando Target Group')

        elb_client.delete_target_group(
            TargetGroupArn=tg_arn
        )
    except:
        print('Nenhum Target Group com esse nome')
        logging.info('Nenhum Target Group com esse nome')

    try:

        print('Deletando auto scaling')
        logging.info('Deletando auto scaling')

        desc_inst = ec2_autoscaling.describe_auto_scaling_instances()

        ec2_autoscaling.update_auto_scaling_group(
            AutoScalingGroupName=asg_nv,
            MinSize=0,
            DesiredCapacity=0,
        )

        for inst in desc_inst['AutoScalingInstances']:
            id_inst = inst['InstanceId']
            ec2_autoscaling.terminate_instance_in_auto_scaling_group(
                InstanceId=id_inst,
                ShouldDecrementDesiredCapacity=True
            )

        ec2_autoscaling.delete_auto_scaling_group(
            AutoScalingGroupName=asg_nv,
            ForceDelete=True
        )
    except:
        print('Nenhum Auto scaling para ser deletado')
        logging.info('Nenhum Auto scaling para ser deletado')

    try:

        print('Deletando Launch Config')
        logging.info('Deletando Launch Config')

        launch_configs = ec2_autoscaling.describe_launch_configurations(
            LaunchConfigurationNames=[
                launch_config_nv,
            ],
        )

        if len(launch_configs['LaunchConfigurations']) > 0:
            ec2_autoscaling.delete_launch_configuration(
                LaunchConfigurationName=launch_config_nv

            )

    except:
        print('Nenhum Launch Configuration criado')
        logging.info('Nenhum Launch Configuration criado')

    logging.info("Todas as depêndencias foram deletadas")
    return "Todas as depêndencias foram deletadas"

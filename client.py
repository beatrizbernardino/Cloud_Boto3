import requests
import datetime


dns = input('Insira o DNS do LoadBalancer: ')
opcoes = input("Digite o método desejado (GET, POST, DELETE): ")

if opcoes == 'GET':

    response = requests.get('http://{0}:80/tasks/tasks/'.format(dns))

elif opcoes == 'POST':

    titulo = input('Insira o título da task: ')
    desc = input('Insira a descrição da task: ')
    x = datetime.datetime.now()
    date = x.strftime('%Y-%m-%dT%H:%M:%S')

    response = requests.post('http://{0}:80/tasks/tasks/'.format(dns),
                             data={'title': titulo, 'pub_date': date, 'description': desc})


elif opcoes == 'DELETE':

    id = input('Insira o id task: ')
    response = requests.delete('http://{0}:80/tasks/tasks/{1}'.format(dns, id))


print("\n Status Code: ", response.status_code)
print(response.json())
print("\n")

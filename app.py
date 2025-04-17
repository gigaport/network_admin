import json
from flask import Flask
from netmiko import ConnectHandler
## 장비관리 라이브러리
from genie.testbed import load
## 장비정보 파싱 라이브러리리
from genie.libs.parser.iosxe.show_interface import ShowInterfaces
from genie.libs.parser.iosxe.show_mcast import ShowIpMroute
from genie.libs.parser.iosxe.show_pim import ShowPimNeighbor


## netmiko connection info
connection_info = {
    "device_type": "cisco_xe",
    "host": "50.5.1.51",
    "username": "125003",
    "password": "Swr278577@",
    "port": 22
}

app = Flask(__name__)

@app.route('/')
def home():
    get_info()
    return "hello"


def get_info():
    try:
        # start: netmiko connection
        print('Start: Netmiko connection')
        net_connect = ConnectHandler(**connection_info)
        net_connect.enable()
        cmd_list = [
            "show ip mroute",
            "show ip pim neighbor"
        ]

        for idx, cmd in enumerate(cmd_list):
            cli_output = net_connect.send_command(cmd)
            print(f"###### idx : {idx}, cmd : {cmd} ######")
            parse_result(idx, cli_output)

    except Exception as e:
        print(f"Error: {e}")


def parse_result(idx, cli_output):
    if idx == 0:    ## show ip mroute
        parser = ShowIpMroute(device=None)
    elif idx == 1:  ## show ip pim neighbor
        parser = ShowPimNeighbor(device=None)

    parsed_output = parser.parse(output=cli_output)

    json_output = json.dumps(parsed_output, indent=4)
    print(json_output)


if __name__ == '__main__':
    app.run(debug=True)
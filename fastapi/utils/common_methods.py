import json, logging, re, time, sys, os

def OpenJsonFile(path):
    data = {}
    try:
        with open(path, 'rt', encoding='UTF8') as json_file:
            data = json.load(json_file)
    except FileNotFoundError:
        print(f"파일이 존재하지 않습니다: {path}")
    except json.JSONDecodeError:
        print(f"JSON 형식이 잘못되었습니다.: {path}")

    return data
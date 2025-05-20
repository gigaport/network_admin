from http import client
from urllib.parse import urlencode
import random


class Repynery:
    def __init__(self, is_https: bool, host: str, port: int, username: str, password: str):
        # initialize random seed
        random.seed()

        # declare a few variables
        # server connection
        self.is_https = is_https
        self.host = host
        self.port = port
        # user authentication
        self.username = username
        self.password = password
        self.token = ''
        self.tag = ''
        # target data feed and analysis result
        self.feedname = ''
        self.jobid = ''
        self.result = ''

    def login(self) -> int:
        # prepare for request information(headers, body, ......)
        request_headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        parameters = {
            'username': self.username,
            'password': self.password
        }

        # send request
        response = self._request("POST", "/q/login", request_headers, urlencode(parameters))

        # determine success
        if response.status == 200:
            self.token = response.headers['Civet7Token']
            self.tag = "repynery_" + str(random.randrange(4294967295))
        return response.status

    def request_data_generation(self, feedname: str, parameters: dict) -> str:
        # check existence of required parameter(s)
        if "type" not in parameters:
            return "Required parameter(type) not found"
        if parameters["type"] == "topn":
            if "base" not in parameters:
                return "Required parameter(base) not found for topn"
        elif parameters["type"] == "bps2":
            if "internalips" not in parameters:
                return "Required parameter(internalips) not found for bps2"
        elif parameters["type"] == "overview":
            if "internalips" not in parameters:
                return "Required parameter(gatherby) not found for overview"
        # send request
        request_headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Civet7Token': self.token,
            'Civet7Tag': self.tag
        }
        response = self._request("POST", "/q/feed/" + feedname + "/refinery", request_headers, urlencode(parameters))
        response_body = response.read()
        # server returns 202 Accepted when it can start the request
        if response.status == 202:
            # save feed name, get job ID, and return
            self.feedname = feedname
            self.jobid = response_body.splitlines()[1].decode("utf-8")
            return ""
        else:
            return response_body

    def get_result(self, parameters: dict) -> int:
        # sanity check: do we have job ID?
        if self.jobid == '':
            return ""
        # send request
        request_headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Civet7Token': self.token,
            'Civet7Tag': self.tag
        }

        # get response to save response body
        response = self._request("GET", "/q/feed/" + self.feedname + "/refinery/" + self.jobid, request_headers, urlencode(parameters))
        self.result = response.read()
        return response.status

    # internal functions ========================================
    def _request(self, method: str, path: str,
                 headers: dict, body: str) -> client.HTTPResponse:
        result = None
        if self.is_https:
            connector = client.HTTPSConnection(self.host, self.port)
            connector.request(method, path, headers=headers, body=body)
            result = connector.getresponse()
        else:
            connector = client.HTTPConnection(self.host, self.port)
            connector.request(method, path, headers=headers, body=body)
            result = connector.getresponse()
        return result

# ----------------------------------------------------------------------
# mobileapp.py
# Contains MobileApp, a class used to communicate with the MobileApp API
# from the Princeton OIT.
# Credit: vr2amesh https://github.com/vr2amesh/COS333-API-Code-Examples
# ----------------------------------------------------------------------

import requests
import json
import base64
from config import CONSUMER_KEY, CONSUMER_SECRET
from database import Database
from sys import stdout
from time import time


_db = Database()


class MobileApp:

    def __init__(self):
        self.configs = Configs()

    # wrapper function for _getJSON with the courses/courses endpoint.
    # kwargs must contain key "term" with the current term code, as well
    # as one or more of "subject" (department code) and "search" (course
    # title)

    def get_courses(self, **kwargs):
        kwargs['fmt'] = 'json'
        return self._getJSON(self.configs.COURSE_COURSES, **kwargs)

    # wrapper function for _getJSON with the courses/terms endpoint.
    # takes no arguments.

    def get_terms(self):
        return self._getJSON(self.configs.COURSE_TERMS, fmt='json')

    '''
    This function allows a user to make a request to 
    a certain endpoint, with the BASE_URL of 
    https://api.princeton.edu:443/mobile-app

    The parameters kwargs are keyword arguments. It
    symbolizes a variable number of arguments 
    '''

    def _getJSON(self, endpoint, **kwargs):
        tic = time()
        req = requests.get(
            self.configs.BASE_URL + endpoint,
            params=kwargs if "kwargs" not in kwargs else kwargs["kwargs"],
            headers={
                "Authorization": "Bearer " + self.configs.ACCESS_TOKEN
            },
        )
        text = req.text

        _db._add_system_log('mobileapp', {
            'message': f'MobileApp API query',
            'query_time': time() - tic,
            'endpoint': endpoint,
            'args': kwargs
        })

        # Check to see if the response failed due to invalid credentials
        text = self._updateConfigs(text, endpoint, **kwargs)

        return json.loads(text)

    def _updateConfigs(self, text, endpoint, **kwargs):
        if text.startswith("<ams:fault"):
            self.configs._refreshToken(grant_type="client_credentials")

            # Redo the request with the new access token
            req = requests.get(
                self.configs.BASE_URL + endpoint,
                params=kwargs if "kwargs" not in kwargs else kwargs["kwargs"],
                headers={
                    "Authorization": "Bearer " + self.configs.ACCESS_TOKEN
                },
            )
            text = req.text

        return text


class Configs:
    def __init__(self):
        self.CONSUMER_KEY = CONSUMER_KEY
        self.CONSUMER_SECRET = CONSUMER_SECRET
        self.BASE_URL = 'https://api.princeton.edu:443/mobile-app/1.0.0'
        self.COURSE_COURSES = '/courses/courses'
        self.COURSE_TERMS = '/courses/terms'
        self.REFRESH_TOKEN_URL = 'https://api.princeton.edu:443/token'
        self._refreshToken(grant_type='client_credentials')

    def _refreshToken(self, **kwargs):
        req = requests.post(
            self.REFRESH_TOKEN_URL,
            data=kwargs,
            headers={
                'Authorization': 'Basic ' + base64.b64encode(bytes(self.CONSUMER_KEY + ':' + self.CONSUMER_SECRET, 'utf-8')).decode('utf-8')
            },
        )
        text = req.text
        response = json.loads(text)
        self.ACCESS_TOKEN = response['access_token']


if __name__ == '__main__':
    api = MobileApp()
    # print(api.get_courses(term='1214', subject='list'))
    print(api.get_courses(term='1214',
                          search='COS333I'))

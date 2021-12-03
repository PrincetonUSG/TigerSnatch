# ----------------------------------------------------------------------
# mobileapp.py
# Contains MobileApp, a class used to communicate with the MobileApp API
# from the Princeton OIT.
# Credit: vr2amesh https://github.com/vr2amesh/COS333-API-Code-Examples
# ----------------------------------------------------------------------

import requests
import json
import base64
from bs4 import BeautifulSoup
from config import CONSUMER_KEY, CONSUMER_SECRET
from database import Database
from time import time


class MobileApp:
    def __init__(self):
        self.configs = Configs()
        self._db = Database()

    # wrapper function for _getJSON with the courses/courses endpoint.
    # kwargs must contain key "term" with the current term code, as well
    # as one or more of "subject" (department code) and "search" (course
    # title)

    def get_courses(self, **kwargs):
        kwargs["fmt"] = "json"
        return self._getJSON(self.configs.COURSE_COURSES, **kwargs)

    # wrapper function for _getJSON with the courses/terms endpoint.
    # takes no arguments.

    def get_terms(self):
        return self._getJSON(self.configs.COURSE_TERMS, fmt="json")

    def get_course_from_registrar_api(self, **kwargs):
        tic = time()
        req = requests.get(
            self.configs.REGISTRAR_API_URL,
            params=kwargs if "kwargs" not in kwargs else kwargs["kwargs"],
            headers={"Authorization": "Bearer " + self.configs.REGISTRAR_ACCESS_TOKEN},
        )
        if req.status_code != 200:
            self.configs._refreshRegistrarToken()
            req = requests.get(
                self.configs.REGISTRAR_API_URL,
                params=kwargs if "kwargs" not in kwargs else kwargs["kwargs"],
                headers={
                    "Authorization": "Bearer " + self.configs.REGISTRAR_ACCESS_TOKEN
                },
            )
        self._db._add_system_log(
            "registrar",
            {
                "message": "Registrar API query",
                "response_time": time() - tic,
                "endpoint": self.configs.REGISTRAR_API_URL,
                "args": kwargs,
            },
        )
        return json.loads(req.text)

    """
    This function allows a user to make a request to 
    a certain endpoint, with the BASE_URL of 
    https://api.princeton.edu:443/mobile-app

    The parameters kwargs are keyword arguments. It
    symbolizes a variable number of arguments 
    """

    def _getJSON(self, endpoint, **kwargs):
        tic = time()
        req = requests.get(
            self.configs.BASE_URL + endpoint,
            params=kwargs if "kwargs" not in kwargs else kwargs["kwargs"],
            headers={"Authorization": "Bearer " + self.configs.ACCESS_TOKEN},
        )
        text = req.text

        self._db._add_system_log(
            "mobileapp",
            {
                "message": "MobileApp API query",
                "response_time": time() - tic,
                "endpoint": endpoint,
                "args": kwargs,
            },
            log=False,
        )

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
                headers={"Authorization": "Bearer " + self.configs.ACCESS_TOKEN},
            )
            text = req.text

        return text


class Configs:
    def __init__(self):
        self.CONSUMER_KEY = CONSUMER_KEY
        self.CONSUMER_SECRET = CONSUMER_SECRET
        self.BASE_URL = "https://api.princeton.edu:443/mobile-app"
        self.COURSE_COURSES = "/courses/courses"
        self.COURSE_TERMS = "/courses/terms"
        self.REGISTRAR_API_URL = (
            "https://api.princeton.edu/registrar/course-offerings/course-details"
        )
        self.REFRESH_TOKEN_URL = "https://api.princeton.edu:443/token"
        self.REGISTRAR_REFRESH_TOKEN_URL = (
            "https://registrar.princeton.edu/course-offerings"
        )
        self._refreshToken(grant_type="client_credentials")
        self._refreshRegistrarToken()

    def _refreshToken(self, **kwargs):
        req = requests.post(
            self.REFRESH_TOKEN_URL,
            data=kwargs,
            headers={
                "Authorization": "Basic "
                + base64.b64encode(
                    bytes(self.CONSUMER_KEY + ":" + self.CONSUMER_SECRET, "utf-8")
                ).decode("utf-8")
            },
        )
        text = req.text
        response = json.loads(text)
        self.ACCESS_TOKEN = response["access_token"]

    def _refreshRegistrarToken(self):
        req = requests.get(self.REGISTRAR_REFRESH_TOKEN_URL)
        soup = BeautifulSoup(req.text, features="lxml")
        data = soup.find(
            "script", {"data-drupal-selector": "drupal-settings-json"}, text=False
        )
        self.REGISTRAR_ACCESS_TOKEN = json.loads(data.contents[0])["ps_registrar"][
            "apiToken"
        ]


if __name__ == "__main__":
    api = MobileApp()
    # print(api.get_courses(term='1214', subject='list'))
    # print(api.get_courses(term="1214", search="NEU350"))
    print(api.get_course_from_registrar_api(term="1224", course_id="014003"))

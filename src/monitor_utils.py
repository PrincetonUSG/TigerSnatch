# ----------------------------------------------------------------------
# monitor_utils.py
# Contains utilities for the Monitor class for the purpose of
# multiprocessing (top-level functions required).
# ----------------------------------------------------------------------

from database import Database
from mobileapp import MobileApp
from coursewrapper import CourseWrapper
from sys import stderr

# _api = MobileApp()


# gets the latest term code
def get_latest_term():
    return Database().get_current_term_code()[0]


# returns two dictionaries: one containing new class enrollments, one
# containing new class capacities
def get_new_mobileapp_data(term, course, classes, default_empty_dicts=False):
    # the prepended space in catnum is intentional
    data = MobileApp().get_courses(
        term=term, subject=course[:3], catnum=f" {course[3:]}"
    )

    if "subjects" not in data["term"][0]:
        if default_empty_dicts:
            return {}, {}
        raise Exception("no query results")

    new_enroll = {}
    new_cap = {}

    # O(n^2) loop - there is only one subject and course!
    for classid in classes:
        for subject in data["term"][0]["subjects"]:
            for course in subject["courses"]:
                for class_ in course["classes"]:
                    if class_["class_number"] == classid:
                        new_enroll[classid] = int(class_["enrollment"])
                        new_cap[classid] = int(class_["capacity"])
                        break

    return new_enroll, new_cap


# returns course data and parses its data into dictionaries
# ready to be inserted into database collections
def get_course_in_mobileapp(term, course_, curr_time):
    _api = MobileApp()

    # the prepended space in catnum is intentional
    data = _api.get_courses(term=term, subject=course_[:3], catnum=f" {course_[3:]}")

    if "subjects" not in data["term"][0]:
        raise RuntimeError("no query results")

    new_enroll = {}
    new_cap = {}
    entirely_new_enrollments = {}

    # iterate through all subjects, courses, and classes
    for subject in data["term"][0]["subjects"]:
        for course in subject["courses"]:
            courseid = course["course_id"]

            # attempt to detect whether a course has reserved seating
            # registrar_data = _api.get_course_from_registrar_api(
            #     term=term, course_id=courseid
            # )

            # new = {
            #     "courseid": courseid,
            #     "displayname": subject["code"] + course["catalog_number"],
            #     "displayname_whitespace": subject["code"]
            #     + " "
            #     + course["catalog_number"],
            #     "title": course["title"],
            #     "time": curr_time,
            #     "has_reserved_seats": len(
            #         registrar_data["course_details"]["course_detail"][0][
            #             "seat_reservations"
            #         ]
            #     )
            #     != 0,
            # }

            new = {
                "courseid": courseid,
                "displayname": subject["code"] + course["catalog_number"],
                "displayname_whitespace": subject["code"]
                + " "
                + course["catalog_number"],
                "title": course["title"],
                "time": curr_time,
                "has_reserved_seats": False,
            }

            if new["displayname"] != course_:
                continue

            for x in course["crosslistings"]:
                new["displayname"] += "/" + x["subject"] + x["catalog_number"]
                new["displayname_whitespace"] += (
                    "/" + x["subject"] + " " + x["catalog_number"]
                )

            new_mapping = new.copy()
            del new["time"]

            all_new_classes = []
            lecture_idx = 0

            for class_ in course["classes"]:
                meetings = class_["schedule"]["meetings"][0]
                section = class_["section"]

                # skip dummy sections (end with 99)
                if section.endswith("99"):
                    continue

                # skip 0-capacity sections
                if int(class_["capacity"]) == 0:
                    continue

                classid = class_["class_number"]

                new_class = {
                    "classid": classid,
                    "section": section,
                    "type_name": class_["type_name"],
                    "start_time": meetings["start_time"],
                    "end_time": meetings["end_time"],
                    "days": " ".join(meetings["days"]),
                    "enrollment": int(class_["enrollment"]),
                    "capacity": int(class_["capacity"]),
                }

                new_enroll[classid] = int(class_["enrollment"])
                new_cap[classid] = int(class_["capacity"])
                entirely_new_enrollments[classid] = {
                    "classid": classid,
                    "courseid": courseid,
                    "section": section,
                    "enrollment": int(class_["enrollment"]),
                    "capacity": int(class_["capacity"]),
                    "swap_out": [],
                }

                # pre-recorded lectures are marked as 01:00 AM start
                if new_class["start_time"] == "01:00 AM":
                    new_class["start_time"] = "Pre-Recorded"
                    new_class["end_time"] = ""

                # lectures should appear before other section types
                if class_["type_name"] == "Lecture":
                    all_new_classes.insert(lecture_idx, new_class)
                    lecture_idx += 1
                else:
                    all_new_classes.append(new_class)

            for i, new_class in enumerate(all_new_classes):
                new[f'class_{new_class["classid"]}'] = new_class

            break

        else:
            continue

        break

    return new, new_mapping, new_enroll, new_cap, entirely_new_enrollments


# helper method for multiprocessing: generates CourseWrappers after
# querying MobileApp for a given course and classid list
def process(args):
    term, course, classes, courseid = args[0], args[1], args[2], args[3]

    try:
        new_enroll, new_cap = get_new_mobileapp_data(
            term, course, classes, default_empty_dicts=True
        )
    except Exception:
        print("detected malformed JSON - skipping", file=stderr)
        return None
    course_data = CourseWrapper(course, new_enroll, new_cap, courseid)
    print(course_data)
    return course_data

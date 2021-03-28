# ----------------------------------------------------------------------
# monitor.py
# Manages enrollment updates through cross-referencing MobileApp and
# the database. Key class method: get_classes_with_changed_enrollments()
# ----------------------------------------------------------------------

from database import Database
from mobileapp import MobileApp
from multiprocess import Pool
from os import cpu_count
from time import time
from sys import stderr
from monitor_utils import get_latest_term, process, get_course_in_mobileapp
from config import COURSE_UPDATE_INTERVAL_MINS


class Monitor:
    def __init__(self):
        self._db = Database()

    # organizes all waited-on classes into groups by their parent course

    def _construct_waited_classes(self):
        waited_classes = list(self._db.get_waited_classes())
        data = {}

        for class_ in waited_classes:
            classid = class_['classid']
            deptnum = self._db.classid_to_course_deptnum(classid)

            print('adding classid', classid, 'from', deptnum)

            if deptnum in data:
                data[deptnum].append(classid)
            else:
                data[deptnum] = [classid]

        self._waited_classes = data

    # constructs CourseWrapper objects for all course buckets as
    # specified in _construct_waited_classes()

    def _analyze_classes(self):
        term = get_latest_term()
        process_args = []

        for course, classes in self._waited_classes.items():
            process_args.append([term, course, classes])

        # alleviate MobileApp bottleneck using multiprocessing
        with Pool(cpu_count()) as pool:
            all_data = pool.map(process, process_args)

        # for course in all_data:
        #     for classid in course._new_enroll:
        #         print('updating enrollment for',
        #               course._course_deptnum, 'class', classid)
        #         self._db.update_enrollment(classid,
        #                                    course._new_enroll[classid],
        #                                    course._new_cap[classid])

        self._waited_course_wrappers = all_data

    # generates, caches, and returns a dictionary in the form:
    # {
    #   classid1: n_slots_available,
    #   classid2: n_slots_available,
    #   ...
    # }
    # the result is to be used to determine to whom notifications are to
    # be sent. this method also updates the applicable enrollment data
    # in the enrollments collection.

    def get_classes_with_changed_enrollments(self):
        try:
            return self._changed_enrollments
        except:
            print('cached enrollments data not found; performing analysis')

        tic = time()

        self._construct_waited_classes()
        try:
            self._waited_classes
        except:
            raise RuntimeError('missing _waited_classes')

        self._analyze_classes()
        try:
            self._waited_course_wrappers
        except:
            raise RuntimeError('missing _waited_course_wrappers')

        data = {}
        for course in self._waited_course_wrappers:
            print('generating class enrollment delta for',
                  course.get_course_deptnum())

            for class_, n_slots in course.get_available_slots().items():
                data[class_] = n_slots

        self._changed_enrollments = data
        print(f'success: approx. {round(time()-tic)} seconds')
        print('enrollments data has been cached; re-call this method to retrieve the cached version')
        return self._changed_enrollments

    # updates all course data if it has been 2 minutes since last update

    def pull_course_updates(self, courseid):
        try:
            time_last_updated = self._db.get_course_time_updated(courseid)
        except Exception as e:
            print(e, file=stderr)
            return

        # if it hasn't been 2 minutes since last update, do not update
        curr_time = time()
        if curr_time - time_last_updated < COURSE_UPDATE_INTERVAL_MINS*60:
            print(
                f'no course update - it hasn\'t been {COURSE_UPDATE_INTERVAL_MINS} minutes since last update for course {courseid}')
            return

        # update time immediately
        try:
            self._db.update_course_time(courseid, curr_time)
        except Exception as e:
            print(e, file=stderr)

        current_term_code = get_latest_term()

        ######################### REMOVE LATER #########################
        current_term_code = '1214'
        ################################################################

        try:
            displayname = self._db.courseid_to_displayname(courseid)
            new_course, new_mapping, new_enroll, new_cap = get_course_in_mobileapp(
                current_term_code, displayname, curr_time)

            # if no changes to course info, do not update
            if new_course == self._db.get_course(courseid):
                print(
                    f'no course update - course data hasn\'t changed for {courseid}')
                return

            # update course data in db
            print(
                f'yes course update - updated course entry in database for {courseid}')
            self._db.update_course_all(courseid, new_course,
                                       new_mapping, new_enroll, new_cap)
        except Exception as e:
            print(e, file=stderr)


if __name__ == '__main__':
    monitor = Monitor()
    print(monitor.get_classes_with_changed_enrollments())
    # call again to retrieve cached version
    print('cached version should print directly beneath this:')
    print(monitor.get_classes_with_changed_enrollments())

# ----------------------------------------------------------------------
# notify.py
# Sends users emails or text messages about enrollment updates
# ----------------------------------------------------------------------

from sendgrid import SendGridAPIClient
from sys import stderr
from twilio.rest import Client
from config import (
    SENDGRID_API_KEY,
    TS_EMAIL,
    TWILIO_PHONE,
    TWILIO_SID,
    TWILIO_TOKEN,
    TS_DOMAIN,
)


class Notify:
    # initializes Notify, fetching all information about a given classid
    # to format and send an email to the first student on the waitlist
    # for that classid

    def __init__(self, classid, n_new_slots, db):
        self._classid = classid
        self.db = db
        try:
            (
                self._deptnum,
                self._title,
                self._sectionname,
                self._courseid,
            ) = db.classid_to_classinfo(classid)
            self._has_reserved_seats = db.does_course_have_reserved_seats(
                self._courseid
            )
            self._coursename = f"{self._deptnum}: {self._title}"
            self._netids = db.get_class_waitlist(classid)["waitlist"]

            user_log = (
                f"{n_new_slots} spots available in {self._deptnum} {self._sectionname}"
            )
            self._emails = []
            self._phones = []
            for netid in self._netids:
                self._emails.append(db.get_user(netid, "email"))
                self._phones.append(db.get_user(netid, "phone"))
                db.update_user_waitlist_log(netid, user_log)
        except:
            raise Exception(
                f"unable to get notification data for subscriptions of class {classid}"
            )

    # returns the netIDs of this Notify object

    def get_netids(self):
        return self._netids

    # returns the phone numbers of this Notify object

    def get_phones(self):
        return self._phones

    # returns the deptnum + section name of this Notify object

    def get_name(self):
        return f"{self._deptnum} {self._sectionname}"

    # sends a formatted email

    def send_emails_html(self):
        try:
            for i in range(len(self._emails)):
                if self._has_reserved_seats:
                    if self.db.get_user_auto_resub(self._netids[i]):
                        # yes auto-resub | yes reserved seats
                        template_id = "d-b32c7a8c99f2491899322ced801b216b"
                    else:
                        # no auto-resub | yes reserved seats
                        template_id = "d-632e8760499b40d680742b9acdb8d129"
                else:
                    if self.db.get_user_auto_resub(self._netids[i]):
                        # yes auto-resub | no reserved seats
                        template_id = "d-c04bc32123ea45ec80889919cc5c377e"
                    else:
                        # no auto-resub | no reserved seats
                        template_id = "d-2607514c41ef48cdb649bad3d4f0c660"

                data = {
                    "personalizations": [
                        {
                            "to": [{"email": self._emails[i]}],
                            "dynamic_template_data": {
                                "netid": self._netids[i],
                                "sectionname": self._sectionname,
                                "coursename": self._coursename,
                                "deptnum": self._deptnum,
                                "tigerhub_url": "https://phubprod.princeton.edu/psp/phubprod/?cmd=start",
                                "dashboard_url": f"{TS_DOMAIN}/dashboard?&skip",
                                "course_url": f"{TS_DOMAIN}/course?query=&courseid={self._courseid}&skip",
                            },
                        }
                    ],
                    "from": {"email": TS_EMAIL, "name": "TigerSnatch"},
                    "template_id": template_id,
                }

                SendGridAPIClient(SENDGRID_API_KEY).client.mail.send.post(
                    request_body=data
                )

            return True
        except Exception as e:
            print(e, file=stderr)
            return False

    # sends an SMS

    def send_sms(self):
        reserved = "This course has reserved seats, so enrollment may not be possible. "
        msg_unsubbed = f"{self._sectionname} in {self._deptnum} has open spots! {reserved if self._has_reserved_seats else ''}Resubscribe: {TS_DOMAIN}/course?courseid={self._courseid}&skip"
        msg_resubbed = f"{self._sectionname} in {self._deptnum} has open spots! {reserved if self._has_reserved_seats else ''}Unsubscribe: {TS_DOMAIN}/dashboard?&skip"
        try:
            for i, phone in enumerate(self._phones):
                is_auto_resub = self.db.get_user_auto_resub(self._netids[i])
                if phone != "":
                    Client(TWILIO_SID, TWILIO_TOKEN).api.account.messages.create(
                        to=f"+1{phone}",
                        from_=TWILIO_PHONE,
                        body=(msg_resubbed if is_auto_resub else msg_unsubbed),
                    )
                if not is_auto_resub:
                    self.db.remove_from_waitlist(self._netids[i], self._classid)
            return True
        except Exception as e:
            print(e, file=stderr)
            return False

    def __str__(self):
        ret = "\nNotifications:\n"
        ret += f"\tNetIDs:\t\t{self._netids}\n"
        ret += f"\tEmails:\t\t{self._emails}\n"
        ret += f"\tPhones:\t\t{self._phones}\n"
        ret += f"\tCourse:\t\t{self._coursename}\n"
        ret += f"\tSection:\t{self._sectionname}\n"
        ret += f"\tClassID:\t{self._classid}"
        return ret


if __name__ == "__main__":
    from database import Database

    db = Database()
    n = Notify("41337", 1, db)
    n.send_emails_html()

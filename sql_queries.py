"""
jirabot v0.6
Angus L'Herrou
piraka@brandeis.edu
github.com/angus-lherrou/jirabot

SQL queries and setup function.

Table `teams`:
+--------------+---------------+------+-----+---------+-------+
| Field        | Type          | Null | Key | Default | Extra |
+--------------+---------------+------+-----+---------+-------+
| team_no      | varchar(64)   | NO   | PRI | NULL    |       |
| url          | varchar(2048) | YES  |     | NULL    |       |
| error_sent   | tinyint(1)    | NO   |     | 0       |       |
| access_token | varchar(128)  | NO   |     | NULL    |       |
+--------------+---------------+------+-----+---------+-------+

Table `messages`:
+------------+--------------+------+-----+---------+-------+
| Field      | Type         | Null | Key | Default | Extra |
+------------+--------------+------+-----+---------+-------+
| team_no    | varchar(64)  | NO   | PRI | NULL    |       |
| channel_id | varchar(64)  | NO   | PRI | NULL    |       |
| msg_id     | varchar(128) | NO   | PRI | NULL    |       |
| payload    | mediumtext   | NO   |     | NULL    |       |
| tickets    | mediumtext   | NO   |     | NULL    |       |
+------------+--------------+------+-----+---------+-------+
"""
import getpass
from collections import namedtuple

import mysql.connector
from mysql.connector import MySQLConnection

Queries = namedtuple('Queries', ['insert_new_team',
                                 'update_url',
                                 'update_error',
                                 'team_exists',
                                 'select_url_and_error',
                                 'select_access_token',
                                 'insert_new_message',
                                 'update_message_payload',
                                 'delete_message',
                                 'select_messages',
                                 'select_single_message',
                                 'select_payload_url_and_tickets'])

QUERIES = Queries(
    insert_new_team=("INSERT INTO teams "
                     "(team_no, access_token) "
                     "VALUES (%s, %s)"),

    update_url=("UPDATE teams "
                "SET url = %s "
                "WHERE team_no = %s"),

    update_error=("UPDATE teams "
                  "SET error_sent = %s "
                  "WHERE team_no = %s"),

    team_exists=("SELECT team_no "
                 "FROM teams "
                 "WHERE team_no = %s"),

    select_url_and_error=("SELECT url, error_sent "
                          "FROM teams "
                          "WHERE team_no = %s"),

    select_access_token=("SELECT access_token "
                         "FROM teams "
                         "WHERE team_no = %s"),

    insert_new_message=("INSERT INTO messages "
                        "(team_no, channel_id, msg_id, payload, tickets) "
                        "VALUES (%s, %s, %s, %s, %s)"),

    update_message_payload=("UPDATE messages "
                            "SET payload = %s, tickets = %s "
                            "WHERE (team_no, channel_id, msg_id) = (%s, %s, %s)"),

    delete_message=("DELETE FROM messages "
                    "WHERE (team_no, channel_id, msg_id) = (%s, %s, %s)"),

    select_messages=("SELECT msg_id "
                     "FROM messages "
                     "WHERE (team_no, channel_id) = (%s, %s)"),

    select_single_message=("SELECT * "
                           "FROM messages "
                           "WHERE (team_no, channel_id, msg_id) = (%s, %s, %s)"),

    select_payload_url_and_tickets=("SELECT payload, url, tickets "
                                    "FROM messages AS M, teams AS T "
                                    "WHERE T.team_no = M.team_no "
                                    "AND (M.team_no, M.channel_id, M.msg_id) = (%s, %s, %s)")
)


def establish_cnx() -> MySQLConnection:
    """
    Prompt the user up to 3 times to enter the database password.
    :return: a MySQLConnection object
    """
    cnx = None
    attempts = 0
    exception = None
    while attempts < 3 and cnx is None:
        try:
            cnx = mysql.connector.connect(
                user='root', database='jirabot',
                password=getpass.getpass(prompt="Enter password for MySQL database: ")
            )
        except mysql.connector.errors.ProgrammingError as ex:
            exception = ex
            attempts += 1
            print(f"Incorrect password (attempt {attempts} of 3)")
        else:
            break
    if attempts == 3:
        raise exception
    print("Authenticated successfully.")
    return cnx

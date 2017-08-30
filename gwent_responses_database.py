# coding=UTF-8

"""Module used to transfer from usage of dictionaries to databases for the bot to use."""

__author__ = 'Jonarzz'


import sqlite3
import os
import datetime
import re

from responses_wiki import gwent_wiki_parser as parser
import gwent_responses_properties as properties


SCRIPT_DIR = os.path.dirname(__file__)


def create_responses_database():
    """Method that creates an SQLite database with pairs response-link
    based on the JSON file with such pairs which was used before."""
    #responses_dictionary = parser.dictionary_from_file(properties.RESPONSES_FILENAME)

    conn = sqlite3.connect('responses.db')
    curse = conn.cursor()

    curse.execute('CREATE TABLE IF NOT EXISTS responses (response text, link text, hero text, hero_id integer, stripped text)')
    # This was from the original Dota bot... but wasn't necessary for me at the moment. Leaving it commented because it was kinda important.
    #for key, value in responses_dictionary.items():
        #print(key, value)
    #    c.execute("INSERT INTO responses(response, link) VALUES (?, ?)", (key, value))

    conn.commit()
    curse.close()


def create_comments_database():
    """Method that creates an SQLite database with ids of already checked comments."""
    already_done_comments = load_already_done_comments()

    conn = sqlite3.connect('comments.db', detect_types=sqlite3.PARSE_DECLTYPES)
    curse = conn.cursor()

    curse.execute('CREATE TABLE IF NOT EXISTS comments (id text, date date)')
    for commentid in already_done_comments:
        curse.execute("INSERT INTO comments VALUES (?, ?)", (commentid, datetime.date.today()))

    conn.commit()
    curse.close()


def load_already_done_comments():
    """Method used to load a list of already done comments' IDs from a text file."""
    with open(os.path.join(SCRIPT_DIR, "already_done_comments.txt")) as file:
        already_done_comments = [i for i in file.read().split()]
        return already_done_comments


def delete_old_comment_ids():
    """Method used to remove comments older than a period of time defined in the properties file
    (number corresponding to number of days)."""
    furthest_date = datetime.date.today() - datetime.timedelta(days=properties.NUMBER_OF_DAYS_TO_DELETE_COMMENT)

    conn = sqlite3.connect('comments.db', detect_types=sqlite3.PARSE_DECLTYPES)
    curse = conn.cursor()
    curse.execute("DELETE FROM comments WHERE date < ?", ([str(furthest_date)]))
    conn.commit()
    curse.execute("SELECT Count(*) FROM comments")
    num_of_ids = curse.fetchone()[0]
    curse.close()

    print("COMMENTS DB CLR\nNumber of IDs: " + str(num_of_ids))


def add_hero_specific_responses(endings=None):
    """Method that adds hero specific responses to the responses database.
    If no argument is provided, all responses pages are parsed.
    Argument expected: list of URL path endings (after the "http://dota2.gamepedia.com/")
    pointing to the page with responses."""
    database_connection = sqlite3.connect('responses.db')
    cursor = database_connection.cursor()

    if not endings:
        endings = parser.pages_for_category(parser.CATEGORY)

    for ending in endings:
        responses_dict = parser.create_responses_dict(ending)
        hero_name = parser.short_hero_name_from_url(ending)
        print(hero_name)
        for key, value in responses_dict.items():
            stripped = key.replace(r".", "")
            stripped = stripped.replace(r",", "")
            stripped = stripped.replace(r"'", "")
            stripped = stripped.replace(r"’", "")
            cursor.execute("INSERT INTO responses(response, link, hero, stripped) VALUES (?, ?, ?, ?)", (key, value, hero_name, stripped))
        database_connection.commit()

    cursor.close()


def create_heroes_database():
    """Method that creates a database with hero names and proper css classes names as taken
    from the DotA2 subreddit and hero flair images from the reddit directory. Every hero has its
    own id, so that it can be joined with the hero from responses database."""
    conn = sqlite3.connect('responses.db')
    curse = conn.cursor()
    curse.execute('CREATE TABLE IF NOT EXISTS heroes (id integer primary key autoincrement, name text, img_dir text, css text)')

    flair_file = open('flair.txt', 'r')
    hero_file = open('hero_names.txt', 'r')
    img_file = open('hero_img.txt', 'r')

    flair_match = re.findall(r'"flair flair\-([^ ]+)"', flair_file.read())
    hero_lines = hero_file.readlines()
    img_paths = img_file.readlines()

    for match in flair_match:
        hero_name = ''
        hero_css = ''
        hero_img_path = ''

        for hero_line in hero_lines:
            heroes_match = re.search(r'(.*?): (\w+)', hero_line)
            if match == heroes_match.group(2).lower():
                hero_name = heroes_match.group(1)
                hero_css = match
                break

        for path in img_paths:
            path_match = re.search(r'\/hero\-([a-z]+)', path)
            if hero_name.lower().translate(str.maketrans("", "", " -'")) == path_match.group(1):
                hero_img_path = path.strip()
                break

        curse.execute("INSERT INTO heroes(name, img_dir, css) VALUES (?, ?, ?)", (hero_name, hero_img_path, hero_css))
        conn.commit()

    curse.execute("UPDATE responses SET hero_id = (SELECT heroes.id FROM heroes WHERE responses.hero = heroes.name);")
    conn.commit()
    curse.close()


def add_hero_ids_to_responses():
    """Method that adds hero ids to responses not assigned to specific heroes based on short hero
    name taken from the response link and heroes dictionary."""
    conn = sqlite3.connect('responses.db')
    curse = conn.cursor()

    heroes_dict = parser.dictionary_from_file(properties.HEROES_FILENAME)

    curse.execute("SELECT link FROM responses WHERE hero IS NULL AND hero_id IS NULL")
    links = curse.fetchall()

    for link_tuple in links:
        short_hero_name = parser.short_hero_name_from_url(link_tuple[0])
        try:
            hero_name = heroes_dict[short_hero_name]
        except:
            continue
        curse.execute("SELECT id FROM heroes WHERE name=?", [hero_name])
        hdbid = curse.fetchone()
        if hdbid is None:
            continue
        hero_id = hdbid[0]
        curse.execute("UPDATE responses SET hero_id=? WHERE link=?;", [hero_id, link_tuple[0]])
        conn.commit()

    curse.close()

#if __name__ == '__main__':
    #create_responses_database()
    #create_comments_database()
    #add_hero_specific_responses()
    #create_heroes_database()
    #add_hero_ids_to_responses()
    #add_hero_specific_responses(["Underlord/Responses"])
    #delete_old_comment_ids()

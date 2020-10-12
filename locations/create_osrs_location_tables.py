import requests
from bs4 import BeautifulSoup
import re
import webbrowser
import gspread


class WikiRequests:

    def __init__(self):
        self.locations = {}
        gc = gspread.service_account()
        self.sheet_obj = gc.open("data")
        self.ws = self.sheet_obj.worksheet("data") # Worksheet
        self.rows = {}
        self.load_spread_sheet()

        self.s = requests.session()
        self.s.headers['Cookie'] = "WEBCOOKIES"
        self.s.headers['User-Agent'] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:81.0) Gecko/20100101 Firefox/81.0"

    def parse_template(self, text):
        return_text = []
        capture = False
        t = text.split("\n")
        for line in text.split("\n"):
            if capture is True:
                if bool(re.match("summary:this is a minor edit.*", str(line).lower())):
                    return_text[0] = return_text[0].split("!")[1]
                    return return_text
                else:
                    return_text.append(line)
            else:
                if bool(re.match(".*\{.*", str(line).lower())):
                    capture = True
                    return_text.append(line)
            x=1
        return text

    def get_current_template(self, url):
        t = w.s.request(url=url, method='get')
        soup = BeautifulSoup(t.text, 'html.parser')
        for div in soup.find_all("div"):
            try:
                if div.attrs['class'][0] == 'mw-body-content' and div['id'] != 'siteNotice':
                    return self.parse_template(div.text)
            except:
                pass

    def load_spread_sheet(self):
        self.rows = {
            "all": self.ws.get_all_values(),
            "incomplete": [{"row":row, "line_no": c} for c, row in enumerate(self.ws.get_all_values()) if row[1] == ''],
            "Farcast": [{"row":row, "line_no": c} for c, row in enumerate(self.ws.get_all_values()) if row[1] == 'Farcast']
        }
        self.group_by_monster()
        print(f"There are {len(self.rows['incomplete'])} rows left for : {54*len(self.rows['incomplete'])}k")
        print(f"We completed {len(self.rows['Farcast'])} rows  for : {54 * len(self.rows['Farcast'])}k")

    def update_spreadsheet_as_done(self, final):
        for key in final:
            for row in final[key]['rows']:
                self.ws.update(f"B{row['line_no']+1}", "Farcast")
        self.rows['Farcast'] = [{"row":row, "line_no": c} for c, row in enumerate(self.ws.get_all_values()) if row[1] == 'Farcast']
        print(f"We completed {len(self.rows['Farcast'])} rows  for : {54 * len(self.rows['Farcast'])}k")

    def group_by_monster(self) -> dict:
        ret_dict = {}
        for row in self.rows['incomplete']:
            if row['row'][0] not in list(ret_dict.keys()):
                ret_dict[row['row'][0]] = [row]

            else:
                ret_dict[row['row'][0]].append(row)
        self.rows['grouped'] = ret_dict


    def merge_rows(self, rows):
        final_table = self.parse_template(rows[0]['row'][2])
        final_template = final_table.split("\n")

        for row in rows:
            template = row['row'][2].split("\n")
            tiles = re.findall('\|x:(\d+),y:(\d+)', template[7])
            for tile in tiles:
                final_template[7] = f"{final_template[7]}|x:{tile[0]},y:{tile[1]}"
            x=1
        temp_list = []
        tiles = re.findall('\|x:(\d+),y:(\d+)', final_template[7])
        for tile in tiles:
            if tile not in temp_list:
                temp_list.append(tile)
                if len(temp_list) == 0:
                    final_template[7] = f"|x:{tile[0]},y:{tile[1]}"
                else:
                    final_template[7] = f"{final_template[7]}|x:{tile[0]},y:{tile[1]}"

        return final_template

    def process_creature(self, group):
        loc_group = {}
        print(f"There are {len(group)} spawns for the {group[0]['row'][0]}")
        for c, row in enumerate(group):
            self.process_row(row=row['row'])
            if self.location not in list(loc_group.keys()):
                loc_group[self.location] = [row]
            else:
                loc_group[self.location].append(row)
        final = {}
        for key in loc_group:

            consolidated = self.merge_rows(loc_group[key])
            final[key] = {"consolidated": consolidated, "key": key, "rows": loc_group[key]}
        # if self.update_osrs_wiki(row=loc_group[key][0], consolidated=consolidated):
        if self.update_osrs_creatre_wiki(final=final):
            x=1
            self.update_spreadsheet_as_done(final)
        else:
            x=1

        x=1


    def process_undone(self):
        for row in self.rows['grouped']:
            self.process_creature(self.rows['grouped'][row])


    def process_row(self, row):

        print(f"We are looking for {row[0]}")
        template = row[2].split("\n")


        tile = re.findall('\|x:(\d+),y:(\d+)', template[7])
        plane = re.findall('|plane\s*=\s*(\d+)\s*', template[6])[2]
        url = f"https://explv.github.io/?centreX={tile[0][0]}&centreY={tile[0][1]}&centreZ={plane}&zoom=9"
        webbrowser.open_new_tab(url)
        location = False
        while location is False:
            location = self.get_location()
        template[2] = template[2].replace("FILL ME IN!", self.location)
        template[4] = template[4].replace("FILL ME IN!", str(self.members))
        row[2] = "\n".join(template)
        return row

    def is_page_members(self, url):
        t = self.get_current_template(url=url)
        for row in t:
            if bool(re.match('|members = Yes', row)):
                return True
            elif bool(re.match('|members = No', row)):
                return False


    def get_location(self):
        #
        loc = input('Submit Location')
        # loc = "Tree Gnome Stronghold"

        self.location = f"[[{loc}]]"

        t= f"[[{loc}]]"

        url = f'https://oldschool.runescape.wiki/w/{loc.replace(" ", "_")}'
        edit_url = url + "?action=edit"
        resp = requests.get(url)
        if resp.status_code == 200:
            webbrowser.open_new_tab(url)
            self.members = self.is_page_members(edit_url)
            return True
        else:
            print("Your submission was not valid, please submit again")
            return False

    def has_location_table(self, template):
        track = False
        for row in template:
            if row == '==Locations==':
                track = True
            if track is True:
                if bool(re.match(r"{{LocTableHead}}", row)):
                    return True
        return False

    def get_location_table(self, template):
        track = False
        rows = []
        for c, row in enumerate(template):
            if row == '==Locations==':
                track = True
                rows.append(c)

            else:
                if track is True:
                    if bool(re.match(r".*==.*", row)) or row == '':
                        break
                    rows.append(c)
        table = [row for c, row in enumerate(template) if c in rows]
        return table

    def create_location_table(self, row, empty=False):
        table = ["\n==Locations==\n{{LocTableHead}}" ]
        if empty is False:
            for r in row:
                table.append(f"{r}")
        table.append("{{LocTableBottom}}")
        return table

    def add_row_to_location_table(self, table, row):
        table_bottom = table.pop()
        for r in row:
            table.append(r)
        table.append(table_bottom)
        return table

    def update_osrs_creatre_wiki(self, final):
        for k in final:
            creature = final[k]['rows'][0]['row'][0]
            break
        url = f"https://oldschool.runescape.wiki/w/{creature}?action=edit"
        template = self.get_current_template(url)
        if self.has_location_table(template):
            table = self.get_location_table(template)
        else:
            table = self.create_location_table(empty=True, row=None)
        for key in final:
            table = self.add_row_to_location_table(table=table, row=final[key]['consolidated'])
        webbrowser.open_new_tab(f"https://oldschool.runescape.wiki/w/{creature}?action=edit")
        cleaned = "\n".join(table)
        return True

    def update_osrs_wiki(self, row, consolidated):

        url = f"https://oldschool.runescape.wiki/w/{row['row'][0]}?action=edit"
        template = self.get_current_template(url)
        if self.has_location_table(template):
            table = self.get_location_table(template)
            table = self.add_row_to_location_table(table=table, row=consolidated)
        else:
            table = self.create_location_table(row=consolidated)


        webbrowser.open_new_tab(f"https://oldschool.runescape.wiki/w/{row['row'][0]}?action=edit")
        cleaned = "\n".join(table)
        # print(cleaned)
        x=1
        return True







if __name__ == '__main__':
    url = "https://oldschool.runescape.wiki/w/Aberrant_spectre?action=edit"
    url = "https://oldschool.runescape.wiki/w/Twisted_Banshee?action=edit"

    w = WikiRequests()
    w.process_undone()



    x=1
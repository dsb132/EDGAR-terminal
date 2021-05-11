#!/Users/Jon/anaconda3/envs/trading/bin/python3
from bs4 import BeautifulSoup
# from requests import Session
import sys
import os
import urllib.request
import datetime
import json
import random
import html
import re
import copy


'''
The url given should be that of the page that contains the data files, just give it that, and then read off the hfrefs
'''
base = 'https://www.sec.gov'

class Financials():
	u_agents = [
		"Mozilla/5.0 (Windows; U; Windows NT 6.2) AppleWebKit/532.25.3 (KHTML, like Gecko) Version/5.0.3 Safari/532.25.3",
		"Mozilla/5.0 (Macintosh; U; PPC Mac OS X 10_7_9 rv:3.0; en-US) AppleWebKit/534.32.7 (KHTML, like Gecko) Version/5.0.4 Safari/534.32.7",
		"Opera/9.10 (X11; Linux x86_64; en-US) Presto/2.9.183 Version/10.00",
		"Mozilla/5.0 (iPad; CPU OS 8_2_1 like Mac OS X; en-US) AppleWebKit/532.7.4 (KHTML, like Gecko) Version/3.0.5 Mobile/8B118 Safari/6532.7.4",
		"Mozilla/5.0 (iPhone; CPU iPhone OS 7_0_2 like Mac OS X; sl-SI) AppleWebKit/535.38.4 (KHTML, like Gecko) Version/3.0.5 Mobile/8B114 Safari/6535.38.4",
		"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_5_0 rv:5.0; sl-SI) AppleWebKit/532.48.6 (KHTML, like Gecko) Version/4.0.4 Safari/532.48.6"
		]
	statement_refs = {
		'balancesheet': ['balance', 'sheet', 'sheets', 'financial', 'position'],
		'cashflows': ['cash', 'flow', 'flows'],
		'operations': ['income', 'statement', 'operations', 'loss'],
		'equitychange': ['changes', 'change', 'in', 'stockholders', 'equity'],
		'parenthetical': ['balance', 'sheet', '(parenthetical)', 'parenthetical', 'condensed']
	}
	base = 'https://www.sec.gov'
	def u_agent(self):
		return random.choice(self.u_agents)

	def has_data(self):
		return self._docs_available

	def _pmatch(self, definition, keywords_list):
		if 'statement' not in definition.lower():
			return 0
		elif 'parenthetical' not in definition.lower():
			return 0
		else:
			check_def = self._clean_definition(definition)
			check_def = check_def.split(sep=' ')
			num_matches = 0
			for word in check_def:
				for key in keywords_list:
					if word == key:
						num_matches += 1
			return num_matches

	def _matches(self, definition, keywords_list):
		'''
        :param definition:
        :param keywords_list:
        :return:
        '''
		# statement check
		if 'statement' not in definition.lower():
			return 0
		elif 'parenthetical' in definition.lower():
			return 0
		else:
			check_def = self._clean_definition(definition)
			check_def = check_def.split(sep=' ')
			num_matches = 0
			for word in check_def:
				for key in keywords_list:
					if word == key:
						num_matches += 1
			return num_matches

	def _clean_definition(self, definition):
		'''
        For cleaning up definitions with weird escape characters, sometimes
        these are html entities
        :param definition:
        :return:
        '''
		clean = html.unescape(definition)
		new_str = ''
		for letter in clean:
			if not letter.isalnum():
				if letter == ' ':
					new_str += letter
				else:
					continue
			else:
				new_str += letter
		return new_str.lower()

	def __init__(self, index_url, from_document=False):
		'''
        Given a landing page with the xbrl, will collect filings and create tables
        :param index_url:
        '''
		self._cik = "nothing to see here"
		self._docs_available = False

		self._balance_sheet_ref = None
		self._cash_flow_ref = None
		self._equity_change_ref = None
		self._income_ref = None
		self._parenthetical_ref = None

		self.balance_sheet_context = None
		self.cash_flow_context = None
		self.equity_change_context = None
		self.income_statement_context = None
		self.parenthetical_context = None

		if(from_document):
			with open("saved_bases.json", 'r') as f:
					self._documents = json.load(f)
			self._docs_available = True
		else:
			self._documents = {
				"instance": None,
				"schema": None,
				"calculation": None,
				"presentation": None
			}  # there are more documents but these are the most useful
			self._docs_available = self._get_link_bases(index_url)
		if not self._docs_available:
			return
		self._set_refs()
		# print(self._balance_sheet_ref)
		# print(self._cash_flow_ref)
		# print(self._equity_change_ref)
		# print(self._income_ref)
		# print(self._parenthetical_ref)

		self.balance_sheet = {}
		self.cash_flows = {}
		self.income_statement = {}

		self.balance_sheet['flatlist'] = self.parse_arc(self._balance_sheet_ref)
		self.cash_flows['flatlist'] = self.parse_arc(self._cash_flow_ref)
		self.income_statement['flatlist'] = self.parse_arc(self._income_ref)

		self._table_format(self.balance_sheet, "balance_sheet")
		self._table_format(self.cash_flows, "cash_flows")
		self._table_format(self.income_statement, "income_statement")

		self.balance_sheet_context = self._get_context(self.balance_sheet['flatlist'])
		self.cash_flow_context = self._get_context(self.cash_flows['flatlist'])
		self.income_statement_context = self._get_context(self.income_statement['flatlist'])

		self.load(self.balance_sheet, 'balance_sheet', self.balance_sheet_context)
		self.load(self.cash_flows, 'cash_flows', self.cash_flow_context)
		self.load(self.income_statement, 'income_statement', self.income_statement_context)

		docs = {
			'balance_sheet':self.balance_sheet,
			'cash_flows':self.cash_flows,
			'income_statement':self.income_statement
		}
		with open("qreport.json", 'w') as f:
			json.dump(docs, f, indent=3)

		#need to parse the presentation arc for things like change in equity and the parenthetical statements
		#The other things are probably less important so i don't need to worry about the structure
		return

	def _get_soup(self, url):
		req = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": self.u_agent()}))
		soup = BeautifulSoup(str(req.read(), encoding='utf-8'), 'lxml')
		return soup

	def _get_link_bases(self, index_url):
		soup = self._get_soup(index_url)
		xd_table = soup.find("table",{"class":"tableFile", "summary":"Data Files"})
		if not xd_table:
			print("There are no XBRL documents!")
			return False
		# print(xd_table)
		xrefs = xd_table.find_all("a")
		xrefs = [x.parent.parent for x in xrefs]
		schema_link = base + xrefs[0].find("a")["href"]
		instance_link = base + xrefs[5].find("a")["href"]
		calculation_link = base + xrefs[1].find("a")["href"]
		presentation_link = base + xrefs[4].find("a")["href"]
		self._documents["instance"] = self._get_soup(instance_link)
		self._documents["schema"] = self._get_soup(schema_link)
		self._documents["calculation"] = self._get_soup(calculation_link)
		self._documents["presentation"] = self._get_soup(presentation_link)
		return True

	def _set_refs(self):
		'''
		should use the references from the schema
		:return:
		'''
		roles = self._documents["schema"].find_all("link:roletype")
		for key in self.statement_refs.keys():
			best = {'num_matches': 0, 'item': None}
			for role in roles:
				definition = str(role.find(name='link:definition').text).lower()
				matches = self._matches(definition, self.statement_refs[key])
				if key == 'parenthetical':
					matches = self._pmatch(definition, self.statement_refs[key])
				if matches > best['num_matches']:
					best['num_matches'] = matches
					best['item'] = role.attrs['roleuri']
			if key == 'balancesheet':
				self._balance_sheet_ref = best['item']
			elif key == 'cashflows':
				self._cash_flow_ref = best['item']
			elif key == 'operations':
				self._income_ref = best['item']
			elif key == 'equitychange':
				self._equity_change_ref = best['item']
			elif key == 'parenthetical':
				self._parenthetical_ref = best['item']
		return

	def _camel_case(self, st):
		start_capital = False
		# print(st)
		if not st:
			return []
		elif not len(st):
			return []
		elif st[0].isupper():
			start_capital = True
		stuff = re.split("(?=[A-Z])", st)
		if(start_capital):
			return stuff[1:]
		else:
			return stuff

	def parse_arc(self, reference):
		'''
		should parse the calculation arcs and or presentation arcs to find the information and its structure
		I can do a different kind of parse for statements that don't need to be structured
		:return:
		'''
		def xto(tag):
			return tag["xlink:to"]
		def xfrom(tag):
			return tag["xlink:from"]
		def gaap_split(linktofrom):
			stuff = linktofrom.split(sep='_')
			return stuff[1]
		def brackets(s):
			return '[\'' + s + '\']'
		link = self._documents["calculation"].find("link:calculationlink", {"xlink:role":reference})
		arcs = link.find_all("link:calculationarc") #gets all of the calc arcs
		statement_items = []
		for arc in arcs:
			fro = gaap_split(xfrom(arc))
			to = gaap_split(xto(arc))
			statement_items.append(fro)
			statement_items.append(to)
		statement_items = list(set(statement_items))
		# print(reference)
		# print(json.dumps(statement_items, indent=2))
		new = {}
		for item in statement_items:
			new[item] = {'to': [], 'from': []}

		for item in statement_items:
			for arc in arcs:
				fro = gaap_split(xfrom(arc))
				t = gaap_split(xto(arc))
				if item == fro:
					new[item]['to'].append(t)
				elif item == t:
					new[item]['from'].append(fro)
			new[item]['from'] = list(set(new[item]['from']))
			new[item]['to'] = list(set(new[item]['to']))

		if 'Liabilities' not in statement_items and reference == self._balance_sheet_ref:
			# do something here
			'''
            I thought about doing something with the root addresses, however it would really be easier to
            just insert 'us-gaap:Liabilities' into the 'to' of LiabilitiesandStockholdersEquity

            'us-gaap:Liabilities'[to] should be ['us-gaap:LiabilitiesAndStockholdersEquity']
            '''

			self._missing_liabilities = True
			subs = copy.deepcopy(new["LiabilitiesAndStockholdersEquity"]['to'])
			new['Liabilities'] = {}
			new['Liabilities']['from'] = ["LiabilitiesAndStockholdersEquity"]
			new['Liabilities']['to'] = []
			valid = []
			wrong_stuff = re.compile('^StockholdersEquity')
			for item in subs:
				if not re.match(wrong_stuff, item):
					valid.append(item)
			new["LiabilitiesAndStockholdersEquity"]['to'].append('Liabilities')
			new["LiabilitiesAndStockholdersEquity"]['to'] = [x for x in new["LiabilitiesAndStockholdersEquity"]['to'] if x not in valid]
			new['Liabilities']['to'] = valid

		items_copy = statement_items.copy()
		level_items = {}
		level = 0
		flat_list = []

		while len(items_copy) > 0:
			level_items[str(level)] = []
			if level == 0:
				used = []
				for key in items_copy:
					if len(new[key]['from']) == 0:
						i_tup = (key, new[key], brackets(key))
						l_item = {
							"level":level,
							"key":brackets(key),
							"words":self._camel_case(key),
							"search":key
						}
						flat_list.append(l_item)
						level_items[str(level)].append(i_tup)
						used.append(key)
				for item in used:
					items_copy.remove(item)
				level += 1
			else:
				parents = level_items[str(level - 1)]  # list of tuples
				child_lists = []
				used = []
				for parent in parents:
					child_lists.append(parent[1]['to'])
				for i in range(0, len(child_lists)):
					child_list = child_lists[i]
					parent_address = parents[i][2]
					for child in child_list:
						child_address = parent_address + '''['items']''' + brackets(child)
						c_tup = (child, new[child], child_address)
						level_items[str(level)].append(c_tup)
						l_item = {
							"level":level,
							"key":child_address,
							"words":self._camel_case(child),
							"search":child
						}
						flat_list.append(l_item)
						used.append(child)
				for item in used:
					items_copy.remove(item)
				level += 1
		return flat_list

	def _table_format(self, statement, s_base):
		def new_item():
			return {'items': {}, 'value': None}
		statement['table'] = {}
		base = 'self.' + s_base + '''['table']'''
		for item in statement['flatlist']:
			exec('{}{} = new_item()'.format(base, item['key']))
		return

	def _get_context(self, statement_flatlist):
		def comp_date(ctex):
			date = ctex.find("enddate")
			if not date:
				date = ctex.find("instant")
			return date.text

		example_item = statement_flatlist[0]
		s_item = example_item['search'].lower()[0:90]
		items = self._documents['instance'].find_all(re.compile(s_item))
		ctexts = [x['contextref'] for x in items]
		ctexts = [self._documents['instance'].find("context", {"id":x}) for x in ctexts]
		dates = [comp_date(x) for x in ctexts]
		max_index = dates.index(max(dates))
		return ctexts[max_index]['id']

	def load(self, statement, s_base, ctex):
		base = 'self.' + s_base + '''['table']'''
		for item in statement['flatlist']:
			s_item = item['search'].lower()[0:90]
			# print(s_item)
			# print(ctex)
			val = self._documents['instance'].find(re.compile(s_item), {"contextref":ctex}).text
			if not len(val):
				continue
			exec_string = base + item['key'] + '''['value']''' + " = " + "{}".format(val)
			exec(exec_string)



if __name__ == "__main__":
	index = "https://www.sec.gov/Archives/edgar/data/1621832/000143774921004116/0001437749-21-004116-index.htm"
	f = Financials(index)

# if __name__ == '__main__':
# 	ses = Session()
# 	text = None
# 	# with open('./msftdata/example.html', 'r') as f:
# 	# 	text = f.read()
# 	req = ses.get(sys.argv[1])
# 	text = req.text
# 	soup = BeautifulSoup(text, 'lxml')
# 	tags = soup.find_all()
# 	data_files = None
# 	# for i in range(0, len(tags)):
# 	# 	print("{} : {}".format(i, tags[i]))
# 	for tag in tags:
# 		if tag.find('table', {'class':'tableFile', 'summary':'Data Files'}):
# 			data_files = tag
# 	rows = data_files.find_all('a')
# 	files = []
# 	group_tags = soup.find('div', {'class':"formContent"}).find_all('div')
# 	fdate = None
#
# 	for i in range(len(group_tags)):
# 		if group_tags[i].text == 'Filing Date':
# 			fdate = group_tags[i+1].text
# 			break
# 	fdate = fdate.replace('-', '')
# 	for row in rows:
# 		files.append(row.attrs['href'])
# 	files = [base+x for x in files]
# 	ticker = files[0].split(sep='/')[-1].split(sep='-')[0]
# 	outbase = os.getcwd() + '/' + fdate + ticker
# 	if not os.path.exists(outbase):
# 		os.mkdir(outbase)
#
# 	os.chdir(outbase)
# 	outbase += '/'
# 	for file in files:
# 		outname = file.split(sep='/')[-1]
# 		req = ses.get(file)
# 		with open(outname, mode='w') as f:
# 			f.write(req.text)
# 	print('All done')

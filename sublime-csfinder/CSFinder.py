import sublime, sublime_plugin, os, re

class FileCache(sublime_plugin.EventListener):
	MAX_POOL_SIZE = 1000
	pool = {} 
	def on_post_save(self, view):
		path = view.file_name()
		if path in self.pool:
			del self.pool[path]
	def read(self, path):
		pool = self.pool
		if path in pool:
			text = pool[path]
		else:
			fo = open(path)
			text = fo.read()
			fo.close()
			if len(pool) < self.MAX_POOL_SIZE:
				pool[path]=text
		return text

class LastPlace():
	file_name_list = []
	line_list = []
	def add(self, file_name,line):
		self.file_name_list.append(file_name)
		self.line_list.append(line)

	def pop(self):
		file_name = self.file_name_list.pop()
		line = self.line_list.pop()
		return {"file_name" : file_name, "line" : line}


class ConfigController():
	CONFIG_FILE = "_csfinder.conf"
	pool = {}
	def get_search_dir(self, path):
		dirname = os.path.dirname(path) 
		if dirname in self.pool:
			search_dir = self.pool[dirname]
		else:
			search_dir = self._get_search_dir(path)
			if search_dir:
				self.pool[dirname] = search_dir
		return search_dir		
	def _get_search_dir(self, path):
		curr_dir = os.path.dirname(path)
		test_path = os.path.join(curr_dir, self.CONFIG_FILE)
		if os.path.exists(test_path):
			fo = open(test_path)
			search_dir = fo.readline()
			fo.close()
			if not os.path.exists(search_dir):
				search_dir = curr_dir
			return search_dir
		else:
			if curr_dir != os.path.dirname(curr_dir):
				return self._get_search_dir(curr_dir)
		return None

class CsfinderCommand(sublime_plugin.TextCommand):
	SUFFIX = ".cs"
	fileCache = FileCache()
	config = ConfigController()
	lastPlace = LastPlace()

	def run(self, edit, forward):
		if forward:
			self.lastPlace.add(self.view.file_name(), self.view.substr(self.view.line(self.view.sel()[0]))	)
			#self.lastPlace.file_name = self.view.file_name()
			#self.lastPlace.line = self.view.substr(self.view.line(self.view.sel()[0]))	
			pattern = self.get_click_pattern()
			if pattern:
				if self.view.find(pattern, 0):
					self.show_view(self.view, pattern)
				else:
					match_file = self.get_first_match_file(pattern)
					if match_file:
						match_file_path = match_file[0] + ":" + str(match_file[1])
						view = sublime.active_window().open_file(match_file_path, sublime.ENCODED_POSITION)
						self.show_view(view, pattern)
					else:
						sublime.status_message(" Find nothing")
						curr_file = self.view.file_name()
						search_dir = self.config.get_search_dir(curr_file)
						if not search_dir:
							sublime.status_message(" No or error config file")
							print "[debug] No or error config file \"" + self.config.CONFIG_FILE + "\""
		else:
			viewData = self.lastPlace.pop()
			view = sublime.active_window().open_file(viewData["file_name"], sublime.ENCODED_POSITION)
			self.show_view(view, viewData["line"])

	def get_click_pattern(self):
		curr_file = self.view.file_name()
		if curr_file and curr_file.endswith(self.SUFFIX):
			word = self.view.substr(self.view.word(self.view.sel()[0]))
			word = word.strip()
			if len(word)>0:
				include_ptn = "\\sinclude\\s*:\\s*\"([^\"]*" + word + "[^\"]*)\""
				function_ptn = "\\scall\\s*:\\s*" + word + "\\s*\("
				line = self.view.substr(self.view.line(self.view.sel()[0]))	
				if re.search(include_ptn, line):
					path = re.search(include_ptn, line).group(1)
					self.open_include_file(path)
					p = None
				elif re.search(function_ptn, line):
					p = "\\sdef\\s*:\\s*" + word + "\\s*\("
					print "[debug] click word: " + str(word) + ", search for: function"
				else:
					p = "\\sset\\s*:\\s*" + word + "\\s*="
					print "[debug] click word: " + str(word) + ", search for: var"
				return p
		else:			
			print "[debug] current file isn't a \"" + self.SUFFIX + "\" file, stop search "
		return None	
	def list_dir_files(self, filelist, path):
		if(os.path.isdir(path)):
			for f in os.listdir(path):
				self.list_dir_files(filelist, os.path.join(path, f))
		else:
			filelist.append(path)
	def show_view(self, view, pattern):
		rg = view.find(pattern, 0)
		if rg:
			point = view.line(rg).begin()
			view.show(point, 0)
			view.sel().clear()
			view.sel().add(sublime.Region(point, point))
	def get_first_match_file(self, pattern):
		filelist = []
		search_dir = self.config.get_search_dir(self.view.file_name())
		print "[debug] search dir: " + str(search_dir)
		if search_dir:
			self.list_dir_files(filelist, search_dir)
		for f in filelist:
			if not f.endswith(self.SUFFIX):
				continue
			curr_file = self.view.file_name()
			if f == curr_file:
				continue
			text = self.fileCache.read(f)
			match = re.search(pattern, text)
			if match != None:
				row = len(text[:match.start()].split("\n"))
				return [f, row]
		return None
	def open_include_file(self, path):
		search_dir = self.config.get_search_dir(self.view.file_name())
		path = os.path.join(search_dir, path)
		if os.path.exists(path):
			sublime.active_window().open_file(path)
		else:
			print "[debug] file is not exists: " + path
			sublime.status_message(" Error include path")
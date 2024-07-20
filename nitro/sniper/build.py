# -*- coding: utf-8 -*-
import shutil, os

def dir(name):
	return './' + name + '/'

def make_dir(name):
	try:
		shutil.rmtree(dir(name))
	except FileNotFoundError:
		pass
	except NotADirectoryError:
		os.remove(name)
	os.mkdir(dir(name))

def build(dir, GOARCH, GOOS):
	print(f'🔄 Building with GOARCH: {GOARCH} and GOOS: {GOOS}')
	os.environ['GOARCH'] = GOARCH
	os.environ['GOOS'] = GOOS
	os.system(f'garble build -o ' + dir)

	if GOOS == 'windows':
		fileName = 'sniper.exe'
	else:
		fileName = 'sniper'

	print(f'✅ Built file with name: {fileName}')
	return fileName

CACHE = 'cache'
releases = [
			['release_windows', 'amd64', 'windows'],
			['release_linux', 'amd64', 'linux'],
			['release_mac', 'amd64', 'darwin'],
			['release_linux_arm', 'arm64', 'linux']
		]

make_dir(CACHE)

for release in releases:
	print()
	dirName = release[0]
	fileName = build(dir(CACHE), release[1], release[2])
	print(f'📁 Directory: {dirName}')

	make_dir(dirName)

	# shutil.copy('config.toml', dirName)

	try:
		shutil.move(dir(CACHE) + fileName, dir(dirName))
	except:
		os.remove(dir(CACHE) + fileName)
		shutil.move(dir(CACHE) + fileName, dir(dirName))

	print('📂 Content: ' + ', '.join(os.listdir(dirName)))

shutil.rmtree(dir(CACHE))

os.environ['GOARCH'] = "amd64"
os.environ['GOOS'] = "windows"

print()
print("🦠  Luxury")
print()

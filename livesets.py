
'''
Prints out the contents of a Motif file.

Based on the excellent work done by Chris Webb, who did a lot of helpful
reverse engineering on the Motif file format, and wrote Python code
based on that. I used his work as a starting point for this code.
Link: http://www.motifator.com/index.php/forum/viewthread/460307/

@author:  Michael Trigoboff
@contact: mtrigoboff@comcast.net
@contact: http://spot.pcc.edu/~mtrigobo

Copyright 2012, 2013 Michael Trigoboff.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program as file gpl.txt.
If not, see <http://www.gnu.org/licenses/>.
'''

import collections, os.path, struct, sys

VERSION = '0.1'

SONG_ABBREV =		'Sg'
PATTERN_ABBREV =	'Pt'

FILE_HDR_LGTH =						64
CATALOG_ENTRY_LGTH =			 	 8
BLOCK_HDR_LGTH =				 	12
ENTRY_HDR_LGTH =				 	 8
DATA_HDR_LGTH =						 8
ENTRY_FIXED_SIZE_DATA_LGTH =	 	22

FILE_HDR_ID =		b'YAMAHA-YSFC'
BLOCK_ENTRY_ID =	b'Entr'
BLOCK_DATA_ID =		b'Data'

BANKS = ('PRE1', 'PRE2', 'PRE3', 'PRE4', 'PRE5', 'PRE6', 'PRE7', 'PRE8',
		 'USR1', 'USR2', 'USR3', 'USR4', 'GM',   'GMDR', 'PDR',  'UDR')

# globals (this is just here for documentation)
global catalog, fileVersion, inputStream, mixingVoices, \
	   sampleVoices, voices, waveformTypes

def fileVersionPreMontage():
	return fileVersion[0] < 4

def strFromBytes(bytes):
	strBytes = struct.unpack('> 25x 16s ' + str(len(data) - 41) + 'x', data)
	strBytesDecoded = strBytes.decode('ascii')
	return strBytesDecoded.rstrip('\x00').split('\x00')[0]

def printPerformance(entryName, data):
	print(entryName, len(data))

def printLiveSetBlock(entryName, data):
	print(entryName)
	bPageName = struct.unpack('> 25x 16s ' + str(len(data) - 41) + 'x', data)
	pageNameDecoded = bPageName[0].decode('ascii')
	pageName = pageNameDecoded.rstrip('\x00').split('\x00')[0]
	print('\t' + strFromBytes(bPageName))
	pass

class BlockSpec:
	def __init__(self, ident, name, doFn, needsData):
		self.ident =			ident
		self.name =				name
		self.doFn =				doFn			# what to do with each item of this type
		self.needsData =		needsData

# when printing out all blocks, they will print out in this order
blockSpecs = collections.OrderedDict((
	('ls',  BlockSpec(b'ELST',	'Live Set Blocks',	printLiveSetBlock,	True)),		\
	#('pf',  BlockSpec(b'EPFM',	'Performances',		printPerformance,	True)),		\
	))

def doBlock(blockSpec):
	global catalog
	
	try:
		inputStream.seek(catalog[blockSpec.ident])
	except:
		print('no data of type: %s\n' % (blockSpec.name))
# 		print('no data of type: %s(%s)\n' % (blockSpec.name, blockSpec.ident.decode('ascii')))
		return

	blockHdr = inputStream.read(BLOCK_HDR_LGTH)
	blockIdData, nEntries = struct.unpack('> 4s 4x I', blockHdr)

	assert blockIdData == blockSpec.ident, blockSpec.ident
	
	print(blockSpec.name)

	for _ in range(0, nEntries):
		entryHdr = inputStream.read(ENTRY_HDR_LGTH + ENTRY_FIXED_SIZE_DATA_LGTH)
		entryId, entryLgth, dataOffset = \
			struct.unpack('> 4s I 4x I 14x', entryHdr)
		entryStrs = inputStream.read(entryLgth - ENTRY_FIXED_SIZE_DATA_LGTH)
		assert entryId == BLOCK_ENTRY_ID, BLOCK_ENTRY_ID
		entryStrsDecoded = entryStrs.decode('ascii')
		entryName = entryStrsDecoded.rstrip('\x00').split('\x00')[-1]
		if blockSpec.needsData:
			entryPosn = inputStream.tell()
			dataIdent = bytearray(blockSpec.ident)
			dataIdent[0] = ord('D')
			dataIdent = bytes(dataIdent)
			inputStream.seek(catalog[dataIdent] + dataOffset)
			dataHdr = inputStream.read(DATA_HDR_LGTH)
			dataId, dataLgth = struct.unpack('> 4s I', dataHdr)
			assert dataId == BLOCK_DATA_ID, BLOCK_DATA_ID
			blockData = inputStream.read(dataLgth)
			inputStream.seek(entryPosn)
		else:
			blockData = None
		blockSpec.doFn(entryName, blockData)

def printMontageFile(fileName, selectedItems):
	# globals
	global catalog, fileVersion, inputStream, mixingVoices, \
		   sampleVoices, voices, waveformTypes

	catalog =			{}
	mixingVoices =		[]
	sampleVoices =		[]
	voices =			[]
	
	# open file
	try:
		inputStream = open(fileName, 'rb')
	except IOError:
		errStr = 'could not open file: %s' % fileName
		print(errStr)
		raise Exception(errStr)

	# read file header
	fileHdr = inputStream.read(FILE_HDR_LGTH)
	fileHdrId, fileVersionBytes, catalogSize = struct.unpack('> 16s 16s I 28x', fileHdr)
	assert fileHdrId[0:len(FILE_HDR_ID)] == FILE_HDR_ID, FILE_HDR_ID
	fileVersionStr = fileVersionBytes.decode('ascii').rstrip('\x00')
	fileVersion = tuple(map(int, fileVersionStr.split('.')))
	
	# build catalog
	for _ in range(0, int(catalogSize / CATALOG_ENTRY_LGTH)):
		entry = inputStream.read(CATALOG_ENTRY_LGTH)
		entryId, offset = struct.unpack('> 4s I', entry)
		catalog[entryId] = offset

	print('%s\n' % os.path.basename(fileName))
	if len(selectedItems) == 0:					# print everything
		for blockSpec in blockSpecs.values():
			doBlock(blockSpec)
	else:										# print selectedItems
		# cmd line specifies what to print
		for blockAbbrev in selectedItems:
			try:
				doBlock(blockSpecs[blockAbbrev])
			except KeyError:
				print('unknown data type: %s\n' % blockAbbrev)
	
	inputStream.close()
	print('\n(Montage File v%s, printMontageFile v%s)\n' % (fileVersionStr, VERSION))

help1Str = \
'''
To print Live Sets, type:

   python livesets.py montageFileName

If you want to save the output into a text file, do this:

   python livesets.py ... > outputFileName.txt
'''

help2Str = \
'''
Copyright 2012-2018 Michael Trigoboff.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.'''

if len(sys.argv) == 1:
	# print help information
	print('livesets version %s\n' % VERSION)
	print('by Michael Trigoboff\nmtrigoboff@comcast.net\nhttp://spot.pcc.edu/~mtrigobo')
	print(help1Str)
	for blockFlag, blockSpec in blockSpecs.items():
		print('   %s    %s' % (blockFlag, blockSpec.name.lower()))
	print(help2Str)
	print()
else:
	# process file
	if len(sys.argv) > 2:
		itemFlags = sys.argv[1:-1]
	else:
		itemFlags = ()
	try:
		printMontageFile(sys.argv[-1], itemFlags)
	except Exception as e:
		print('file problem (%s)' % e, file = sys.stderr)

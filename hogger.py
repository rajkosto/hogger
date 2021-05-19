#!/usr/bin/python3
import struct
import sys
import os

scriptName = sys.argv[0]
if len(sys.argv) != 2:
	print("Usage: %s filename.[hog|txt]" % scriptName,file=sys.stderr)
	sys.exit(1)

inputFname = sys.argv[1]
inputFnameAndExt = os.path.splitext(inputFname)
inputExt = ''
if len(inputFnameAndExt) > 1:
	inputExt = inputFnameAndExt[1]

openMode = 'rb'
if inputExt.lower() == '.txt':
	openMode = 'r'

inputFile = False
try:
	inputFile = open(inputFname,openMode)
except IOError:
	print("Error opening main input file: %s" % inputFname,file=sys.stderr)
	sys.exit(2)

def readString(file):
	outBytes = bytearray()
	while True:
		readByte = file.read(1)
		if len(readByte) == 0 or readByte == b'\0':
			break

		outBytes.append(readByte[0])

	return outBytes.decode('latin1')

def writeString(file,text):
	file.write(text.encode('latin1'))
	file.write(b'\0')

fileList = []
if openMode == 'rb': #parse hog
	hdrMtime, hdrNumFiles, hdrListOffset, hdrTextOffset, hdrDataOffset = struct.unpack('<iIIII',inputFile.read(20))

	assert inputFile.tell() == hdrListOffset, "fileList should always be immediately after global header"
	for fileIdx in range(hdrNumFiles+1): #has one extra offset so length of last file can be calculated
		fileOffset = int.from_bytes(inputFile.read(4),'little')
		totalOffset = fileOffset+hdrDataOffset
		fileList.append({ 'offset': totalOffset });
		
	#can calculate lengths now that we have all the offsets
	for fileIdx in range(hdrNumFiles):
		fileList[fileIdx]['length'] = fileList[fileIdx+1]['offset'] - fileList[fileIdx]['offset']
	#remove the last entry since it was only used to calculate offsets
	fileList.pop()

	assert inputFile.tell() == hdrTextOffset, ("text should always be immediately after fileList (tell: %u offset: %u)" % (inputFile.tell(), hdrTextOffset))
	for fileIdx in range(hdrNumFiles):
		fileName = readString(inputFile)
		fileList[fileIdx]['name'] = fileName

	if inputFile.tell() != hdrDataOffset:
		print("file data not immediately following text (tell: %u offset: %u)" % (inputFile.tell(), hdrDataOffset))
		inputFile.seek(hdrDataOffset)
		
	outputDirName = inputFnameAndExt[0]
	if not os.path.isdir(outputDirName):
		os.mkdir(outputDirName)
		
	for fileIdx in range(hdrNumFiles):
		if inputFile.tell() != fileList[fileIdx]['offset']:
			print("file %s not right after previous (tell: %u offset: %u)" % (fileList[fileIdx]['name'], inputFile.tell(), fileList[fileIdx]['offset']))
			inputFile.seek(fileList[fileIdx]['offset'])
		
		outFname = os.path.join(outputDirName,fileList[fileIdx]['name'])
		outFile = False
		try:
			outFile = open(outFname,'wb')
		except IOError:
			print("Error opening output file: %s" % outFname,file=sys.stderr)
			sys.exit(3)
		
		numWritten = 0
		remaining = fileList[fileIdx]['length']		
		while remaining > 0:
			blockSize = 64*1024
			if blockSize > remaining:
				blockSize = remaining
				
			readBytes = inputFile.read(blockSize)
			outFile.write(readBytes)
			numWritten = numWritten + len(readBytes)
			if len(readBytes) < blockSize:
				remaining = 0
			else:
				remaining = remaining - blockSize
		
		outFile.close()
		os.utime(outFname,times=(hdrMtime,hdrMtime))
		assert numWritten == fileList[fileIdx]['length'], "input file must have enough bytes to hold inner file data"
	
	outputTxtName = outputDirName
	if outputTxtName.endswith('\\') or outputTxtName.endswith('/'):
		outputTxtName = outputTxtName[:-1]
	
	inputFile.close()
	outputTxtName = outputTxtName + '.txt'
	outTxtFile = False
	try:
		outTxtFile = open(outputTxtName,'w',encoding='latin1')
	except IOError:
		print("Error opening output txt file: %s" % outTxtFile,file=sys.stderr)
		sys.exit(4)
	
	for fileIdx in range(hdrNumFiles):
		outTxtFile.write(fileList[fileIdx]['name'])
		outTxtFile.write('\n')
		
	outTxtFile.close()
	os.utime(outputTxtName,times=(hdrMtime,hdrMtime))
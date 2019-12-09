#!/usr/bin/env python3

__author__ = "Keenan Nicholson"
__copyright__ = "Copyright 2019"
__license__ = "GNU GPL v3.0"
__version__ = "1.0"

"""Spreadsheet Column Printer

This script allows the user to print to the console all columns in the
spreadsheet. It is assumed that the first row of the spreadsheet is the
location of the columns.

This tool accepts comma separated value files (.csv) as well as excel
(.xls, .xlsx) files.

This script requires that `pandas` be installed within the Python
environment you are running this script in.

This file can also be imported as a module and contains the following
functions:

    * get_spreadsheet_cols - returns the column headers of the file
    * main - the main function of the script
"""


import os, shutil
from os.path import isfile, join
import sys
import io
import time
import argparse
import sqlite3
from PIL import Image
from os import listdir

################################################################################
############################### Helper Functions ###############################

def safeMakeDir(d):
  if os.path.exists(d):
    return
  os.makedirs(d)

def setDir(d):
  safeMakeDir(d)
  os.chdir(d)

# Print iterations progress
def printProgressBar (iteration, total, prefix = '', suffix = '', decimals = 1, length = 100, fill = '█', printEnd = "\r"):
  """
  Call in a loop to create terminal progress bar
  @params:
      iteration   - Required  : current iteration (Int)
      total       - Required  : total iterations (Int)
      prefix      - Optional  : prefix string (Str)
      suffix      - Optional  : suffix string (Str)
      decimals    - Optional  : positive number of decimals in percent complete (Int)
      length      - Optional  : character length of bar (Int)
      fill        - Optional  : bar fill character (Str)
      printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
  """
  percent = ("{0:." + str(decimals) + "f}%").format(100 * (iteration / float(total)))
  percent_fmat = f'{percent:6}'
  filledLength = int(length * iteration // total)
  bar = fill * filledLength + '-' * (length - filledLength)
  print('\r%s |%s| %s %s' % (prefix, bar, percent_fmat, suffix), end = printEnd)
  # Print New Line on Complete
  if iteration == total: 
    print()

def delete_all_in_folder(folder, silent=False):
  if not silent:
    print(f'Clearing output folder "{folder}"...', end="", flush=True)
  for filename in os.listdir(folder):
    file_path = os.path.join(folder, filename)
    try:
      if os.path.isfile(file_path) or os.path.islink(file_path):
        os.unlink(file_path)
      elif os.path.isdir(file_path):
        shutil.rmtree(file_path)
    except Exception as e:
      print('Error: Failed to delete %s. Reason: %s' % (file_path, e))
      exit(1)
  if not silent:
    print('Done')

################################################################################
############################### Helper Functions ###############################


parser = argparse.ArgumentParser(description='Expand MBTiles to image files.')
parser.add_argument('-s', '--source', nargs=1, dest='source', default=['./'],
                      help='select the source directory containing file(s) for expansion (default: %(default)s)')
parser.add_argument('-o', '--output', nargs=1, dest='output', default=['./tiles/'],
                      help='select the output directory (default: %(default)s)')
parser.add_argument('-m', '--max-zoom', dest='max_zoom', nargs=1, default=[-1], type=int,
                      help='specify the highest zoom level (most zoomed in) to expand')
parser.add_argument('--min-zoom', dest='min_zoom', nargs=1, default=[-1], type=int,
                      help='specify the lowest zoom level (least zoomed in) to expand')
parser.add_argument('--extension', dest='extension', nargs=1, default=['.mbtiles'],
                      help='file extension of the MBTile files')
parser.add_argument('-e', '--extrapolate', dest='ext', action='store_true', 
                      help='if --max-zoom is also specified, will extrapolate tiles to the max-zoom setting')
parser.add_argument('--silent', dest='silent', action='store_true', help='silences print output')
parser.add_argument('-c', '--clean', dest='clean', action='store_true', help='cleans output directory first')
parser.add_argument('-y', '--yes', dest='yes', action='store_true', help='answers yes to all questions')

args = parser.parse_args()

# Process input
input_dir = args.source[0]
dirname = args.output[0]
min_zoom = args.min_zoom[0]
max_zoom = args.max_zoom[0]
# print ('Converting MBTile files in "%s" into tiles in local directory "%s"' % (input_dir, dirname))
try:
  onlyfiles = [f for f in listdir(input_dir) if isfile(join(input_dir, f))]
except FileNotFoundError as e:
  print(f'Error: The source folder selection (-s) argument "{input_dir}" could not be found')
  exit(1)
except NotADirectoryError as e:
  print(f'Error: The source folder selection (-s) argument "{input_dir}" is not a directory')
  exit(1)
except PermissionError as e:
  print(f'Error: Premission error trying to access the source folder selection (-s) argument "{input_dir}"')
  exit(1)

try:
  os.makedirs(dirname)
except PermissionError as e:
  print(f'Error: Premission error trying to access the output folder (-o) "{input_dir}"')
  exit(1)
except FileExistsError as e:
  pass

if not os.access(dirname, os.W_OK):
  print(f'Error: Premission error trying to access the output folder (-o) "{input_dir}"')
  exit(1)

files_to_parse = []
names_to_parse = []
parse_message = []

files_exported = []


for file_name in onlyfiles:
  filename, file_extension = os.path.splitext(file_name)
  if file_extension == args.extension[0]:
    files_to_parse.append(input_dir + '/' + file_name)
    names_to_parse.append(file_name)
    try:
      connection = sqlite3.connect(input_dir + '/' + file_name)
      cursor = connection.cursor()
      cursor.execute("SELECT value FROM metadata WHERE name='format'")
      img_format = cursor.fetchone()[0]
      if img_format and (img_format == 'png' or img_format == 'jpg' or img_format == 'jpeg'):
        files_exported.append(file_name)
        cursor.execute("SELECT COUNT(1) FROM TILES")
        l = cursor.fetchone()[0]
        cursor.execute("SELECT DISTINCT zoom_level FROM TILES WHERE 1=1")
        s = []
        for row in cursor:
          s.append(str(row[0]))
        z = ', '.join(s)
        parse_message.append(f' | {l} tiles, zoom levels: {z}')
      elif img_format:
        parse_message.append(f' Error: Unsupported tile format: {img_format}')
      else:
        parse_message.append(f' Error: Missing format metadata')
    except sqlite3.OperationalError as e:
      parse_message.append(f' Error: Operational Error: {str(e)}')

longest_name = 0
for name in names_to_parse:
  if len(name) > longest_name:
    longest_name = len(name)

rows, columns = os.popen('stty size', 'r').read().split()
loading_length = int(columns) - longest_name - 53

if loading_length < 0:
  loading_length = 0


if args.silent is False:
  print('  __  __ ____ _____ _ _             _____                            _           ')
  print(' |  \/  | __ )_   _(_) | ___  ___  | ____|_  ___ __   __ _ _ __   __| | ___ _ __ ')
  print(' | |\/| |  _ \ | | | | |/ _ \/ __| |  _| \ \/ / \'_ \ / _` | \'_ \ / _` |/ _ \ \'__|')
  print(' | |  | | |_) || | | | |  __/\__ \ | |___ >  <| |_) | (_| | | | | (_| |  __/ |   ')
  print(' |_|  |_|____/ |_| |_|_|\___||___/ |_____/_/\_\ .__/ \__,_|_| |_|\__,_|\___|_|   ')
  print('                                              |_|                                ')
  print(f'Source input:    {args.source[0]}')
  print(f'Output location: {args.output[0]}')

  print(f'Files to parse:')
  counter = 0
  for name in names_to_parse:
    n = '{1:{0}}'.format(longest_name, name)
    print(f' {counter:02} > {n}{parse_message[counter]}')
    counter = counter + 1

if files_exported == []:
  print(f'Error: No files to parse were found: Folder: {input_dir}, Extension: {args.extension[0]}')
  exit(1)

if args.silent is False:
  print()

if args.clean:
  if args.silent or args.yes:
    delete_all_in_folder(dirname)
    if args.silent is False:
      print()
  else:
    response = input(f'Are you sure you want to clear the output directory ("{dirname}") [y/N]? ').lower()
    if response == 'y' or response == 'yes' or response == 'yea' or response == 'yeah':
      delete_all_in_folder(dirname)
      if args.silent is False:
        print()
    else:
      print('Retry while omitting the "-c, --clean" argument.')
      exit(1)


# src = 'data/clear_image.png'
# dst = '132/213/444.tif'

# # This creates a symbolic link on python in tmp directory
# os.symlink(src, dst)

# print ("symlink created")

# im = Image.new("RGBA", (256,256), color=None)
# im.save("clear.png", "PNG")

# zooms = [5, 6, 7, 8, 9, 10, 11]
# img_source = '../../../clear.png'
# os.chdir(dirname)
# for z in zooms:
#   setDir(str(z))
#   strz = str(z)
#   for x in range(2**z):
#     print(strz + '-' + str(x))
#     setDir(str(x))
#     for y in range(2**z-1):
#       # print(f'{z}/{x}/{y}')
#       os.symlink(img_source, str(y) + '.png')
#     os.chdir('..')
#   os.chdir('..')

# exit()

for file_name in files_exported:
  input_filename = input_dir + '/' + file_name


  # Database connection boilerplate
  connection = sqlite3.connect(input_filename)
  cursor = connection.cursor()

  cursor.execute("SELECT value FROM metadata WHERE name='format'")
  img_format = cursor.fetchone()

  if img_format:
      if img_format[0] == 'png':
          out_format = '.png'
      elif img_format[0] == 'jpg':
          out_format = '.jpg'
  else:
      out_format = ''

  # The mbtiles format helpfully provides a table that aggregates all necessary info
  cursor.execute("SELECT COUNT(1) FROM TILES")
  l = cursor.fetchone()[0]

  if min_zoom == -1 and max_zoom == -1:
    cursor.execute('SELECT * FROM tiles')
  elif min_zoom == -1 and max_zoom is not -1:
    cursor.execute(f'SELECT * FROM tiles WHERE zoom_level <= {max_zoom}')
  elif min_zoom is not -1 and max_zoom == -1:
    cursor.execute(f'SELECT * FROM tiles WHERE zoom_level >= {min_zoom}')
  elif min_zoom is not -1 and max_zoom is not -1:
    cursor.execute(f'SELECT * FROM tiles WHERE zoom_level <= {max_zoom} AND zoom_level >= {min_zoom}')

  printProgressBar(0, l, prefix = 'Progress:', suffix = 'Complete', length = loading_length)
  i = 0
  os.chdir(dirname)
  fn = '{1:{0}}'.format(longest_name, file_name)
  title = ''
  for row in cursor:
    setDir(str(row[0]))
    setDir(str(row[1]))
    image_name = str((2**row[0]) - 1 - row[2]) + out_format
    if os.path.exists(image_name):
      # print(F'{row[0]}/{row[1]}/{image_name}')
      im1 = Image.open(image_name).convert("RGBA")
      im2 = Image.open(io.BytesIO(row[3])).convert("RGBA")
      im1.paste(im2, (0, 0), im2)
      im1.save(image_name)
    else:
      output_file = open(image_name, 'wb')
      output_file.write(row[3])
      output_file.close()
    
    if i%5 == 0:
      title = f'{fn} : {row[0]}/{row[1]}/{image_name}     '
      printProgressBar(i, l, prefix = 'Progress:', suffix = title, length = loading_length)
    i = i + 1
    os.chdir('..')
    os.chdir('..')
  os.chdir('..')
  tmp=f'{fn} : [Complete]'
  tmp = '{1:{0}}'.format(len(title) + 3, tmp)
  printProgressBar(l, l, prefix = 'Progress:', suffix = tmp, length = loading_length)
print ('Done!')

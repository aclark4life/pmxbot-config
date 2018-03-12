"""
Install pmxbot on DCPython's Xenial server
"""

import getpass

from fabric.contrib import files
from fabric import api
from fabric.api import sudo, run, env

host = 'kafka'
domain = 'dcpython.org'
env.hosts = ['.'.join((host, domain))]

python = 'python3.6'


@api.task
def install_config():
	db_pass = getpass.getpass('MongoDB password for pmxbot [skip]> ')
	twilio_token = getpass.getpass('Token for twilio [skip]> ')
	google_trans_key = getpass.getpass('Google Translate key [skip]> ')
	wolframalpha_key = getpass.getpass('Wolfram|Alpha key [skip]> ')
	sudo('mkdir -p /etc/pmxbot')
	files.upload_template(
		'pmxbot.conf', '/etc/pmxbot/main.conf',
		use_sudo=True)
	files.upload_template(
		'web.conf', '/etc/pmxbot/web.conf',
		use_sudo=True)
	if not files.exists('/etc/pmxbot/server.conf'):
		files.upload_template(
			'server.conf', '/etc/pmxbot/server.conf',
			use_sudo=True)
	if db_pass or not files.exists('/etc/pmxbot/database.conf'):
		files.upload_template(
			'database.conf', '/etc/pmxbot/database.conf',
			context=dict(password=db_pass), use_sudo=True, mode=0o600)
	if twilio_token or not files.exists('/etc/pmxbot/twilio.conf'):
		files.upload_template(
			'twilio.conf', '/etc/pmxbot/twilio.conf',
			context=dict(token=twilio_token), use_sudo=True, mode=0o600)
	if google_trans_key or not files.exists('/etc/pmxbot/trans.conf'):
		files.upload_template(
			'trans.conf', '/etc/pmxbot/trans.conf',
			context=dict(key=google_trans_key), use_sudo=True, mode=0o600)
	if wolframalpha_key or not files.exists('/etc/pmxbot/wolframalpha.conf'):
		files.upload_template(
			'wolframalpha.conf', '/etc/pmxbot/wolframalpha.conf',
			context=dict(key=wolframalpha_key), use_sudo=True, mode=0o600)


@api.task
def install_python():
	sudo('apt-add-repository -y ppa:fkrull/deadsnakes')
	sudo('apt update')
	sudo('apt -q install -y {python}-venv'.format_map(globals()))


packages = ' '.join([
	'pmxbot[irc,mongodb,viewer]',
	'excuses',
	'popquotes',
	'wolframalpha',
	'jaraco.pmxbot',
	'pymongo',
	'chucknorris',
	'pmxbot-haiku',
	'twilio',
	'motivation',
	'jaraco.translate',
])

install_root = '/opt/pmxbot'


@api.task
def install_pmxbot():
	"Install pmxbot into a venv at install_root"
	sudo(f'{python} -m venv {install_root}')
	sudo(f'{install_root}/bin/pip install -U setuptools pip')
	sudo(f'{install_root}/bin/pip install -U {packages}')


@api.task
def install_systemd_service():
	files.upload_template(
		'pmxbot.service',
		'/etc/systemd/system',
		context=globals(),
		use_sudo=True,
	)
	sudo('systemctl restart pmxbot')
	sudo('systemctl enable pmxbot')


@api.task
def install_systemd_web_service():
	files.upload_template(
		'web.conf', '/etc/pmxbot/web.conf',
		use_sudo=True)
	files.upload_template(
		'pmxbot.web.service',
		'/etc/systemd/system',
		context=globals(),
		use_sudo=True,
	)
	sudo('systemctl restart pmxbot.web')
	sudo('systemctl enable pmxbot.web')


@api.task
def update():
	install_pmxbot()
	sudo('systemctl restart pmxbot')
	sudo('systemctl restart pmxbot.web')


@api.task
def ensure_fqdn():
	"""
	Ensure 'hostname -f' returns a fully-qualified hostname.
	"""
	hostname = run('hostname -f')
	if '.' in hostname:
		return
	cmd = 'sed -i -e "s/{hostname}/{hostname}.{domain} {hostname}/g" /etc/hosts'
	cmd = cmd.format(hostname=hostname, domain=domain)
	sudo(cmd)


@api.task
def bootstrap():
	ensure_fqdn()
	install_config()
	install_python()
	install_pmxbot()
	install_systemd_service()

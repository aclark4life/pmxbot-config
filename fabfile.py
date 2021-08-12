"""
Install pmxbot on DCPython's Xenial server
"""

import getpass
import tempfile
import pathlib
import io

import keyring
from fabric import task

host = 'kafka2'
domain = 'dcpython.org'
hosts = [f'{host}.{domain}']

python = 'python3.8'


def upload_template(c, src, dest, *, mode=None, **context):
	rnd_name = next(tempfile._get_candidate_names())
	tmp_dest = f'/tmp/{rnd_name}'
	template = pathlib.Path(src).read_text()
	content = template % context
	stream = io.StringIO(content)
	c.put(stream, tmp_dest)
	if is_dir(c, dest):
		dest = pathlib.PurePosixPath(dest, pathlib.Path(src).name)
	c.sudo(f'mv "{tmp_dest}" "{dest}"')
	if mode is not None:
		mode_str = oct(mode)[2:]
		c.run(f'chmod {mode_str} {dest}')


def exists(c, candidate):
	cmd = f'test -f "{candidate}"'
	return c.run(cmd, warn=True)


def is_dir(c, candidate):
	cmd = f'test -d "{candidate}"'
	return c.run(cmd, warn=True)


def sudo(c, command):
	return c.sudo(command)


@task(hosts=hosts)
def install_config(c):
	bot_pass = keyring.get_password('https://libera.chat', 'pmxbot')
	db_pass = keyring.get_password(
		'mongodb+srv://pmxbot.gsemc.mongodb.net/dcpython', 'pmxbot')
	twilio_token = keyring.get_password(
		'twilio', 'AC00c9739a1539392c4a97f5dc3f5d94c2')
	google_trans_key = keyring.get_password('Google Translate', 'pmxbot')
	wolframalpha_key = keyring.get_password(
		'https://api.wolframalpha.com/', 'jaraco')
	sudo(c, 'mkdir -p /etc/pmxbot')
	upload_template(
		c, 'pmxbot.conf', '/etc/pmxbot/main.conf',
		password=bot_pass,
	)
	upload_template(c, 'web.conf', '/etc/pmxbot/web.conf')
	upload_template(c, 'server.conf', '/etc/pmxbot/server.conf')
	upload_template(
		c, 'database.conf', '/etc/pmxbot/database.conf',
		password=db_pass, mode=0o600)
	upload_template(
		c,
		'twilio.conf', '/etc/pmxbot/twilio.conf',
		token=twilio_token, mode=0o600)
	upload_template(
		c,
		'trans.conf', '/etc/pmxbot/trans.conf',
		key=google_trans_key, mode=0o600)
	upload_template(
		c,
		'wolframalpha.conf', '/etc/pmxbot/wolframalpha.conf',
		key=wolframalpha_key, mode=0o600)


@task(hosts=hosts)
def install_python(c):
	c.sudo('yum install -y amazon-linux-extras')
	c.sudo(f'amazon-linux-extras enable {python}')
	c.sudo('yum install -y python3.8')


packages = ' '.join([
	'pmxbot[irc,mongodb,viewer]',
	'excuses',
	'popquotes',
	'wolframalpha',
	'jaraco.pmxbot',
	'pmxbot.webhooks',
	'pmxbot.saysomething',
	'pymongo',
	'chucknorris',
	'pmxbot-haiku',
	'twilio',
	'motivation',
	'jaraco.translate',
])

install_root = '/opt/pmxbot'


@task(hosts=hosts)
def install_pmxbot(c):
	"Install pmxbot into a venv at install_root"
	sudo(c, f'{python} -m venv {install_root}')
	sudo(c, f'{install_root}/bin/pip install -U setuptools pip')
	sudo(c, f'{install_root}/bin/pip install --upgrade-strategy=eager -U {packages}')


@task(hosts=hosts)
def install_systemd_service(c):
	upload_template(
		c,
		'pmxbot.service',
		'/etc/systemd/system',
		**globals(),
	)
	sudo(c, 'systemctl restart pmxbot')
	sudo(c, 'systemctl enable pmxbot')


@task(hosts=hosts)
def install_systemd_web_service(c):
	upload_template(
		c,
		'web.conf', '/etc/pmxbot/web.conf',
	)
	upload_template(
		c,
		'pmxbot.web.service',
		'/etc/systemd/system',
		**globals(),
	)
	sudo(c, 'systemctl restart pmxbot.web')
	sudo(c, 'systemctl enable pmxbot.web')


@task(hosts=hosts)
def update(c):
	install_pmxbot(c)
	sudo(c, 'systemctl restart pmxbot')
	sudo(c, 'systemctl restart pmxbot.web')


@task(hosts=hosts)
def ensure_fqdn(c):
	"""
	Ensure 'hostname -f' returns a fully-qualified hostname.
	"""
	hostname = c.run('hostname -f')
	if '.' in hostname.stdout:
		return
	cmd = f'sed -i -e "s/{hostname}/{hostname}.{domain} {hostname}/g" /etc/hosts'
	sudo(c, cmd)


@task(hosts=hosts)
def configure_journald(c):
	"""
	Configure journald to use the large volume for logs so the
	logs can be persisted for much longer.
	"""
	c.sudo('mkdir -p /var/log/journal')


@task(hosts=hosts)
def bootstrap(c):
	ensure_fqdn(c)
	install_config(c)
	install_python(c)
	install_pmxbot(c)
	install_systemd_service(c)
	configure_journald(c)

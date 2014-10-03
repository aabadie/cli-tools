""" Integration tests for cli-tools """

# pylint:disable=I0011,too-many-public-methods
# pylint:disable=I0011,attribute-defined-outside-init
# pylint:disable=I0011,invalid-name

#
# Test that may be added:
#  * use node commands
#  * Multi-wsn/m3-sites experiments and validate outputs
#  * Validates JSON outputs
#
#

from __future__ import print_function
import os
import sys
import json
import shlex
import time
import runpy
import unittest
import logging


LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(logging.INFO)

_FMT = logging.Formatter('%(asctime)s :: %(levelname)s :: %(message)s')
_HANDLER = logging.StreamHandler()
_HANDLER.setFormatter(_FMT)
LOGGER.addHandler(_HANDLER)

from tempfile import NamedTemporaryFile

try:
    # pylint:disable=I0011,F0401,E0611
    from mock import patch
    from cStringIO import StringIO
except ImportError:  # pragma: no cover
    from unittest.mock import patch  # pylint:disable=I0011,F0401,E0611
    from io import StringIO


class TestCliToolsExperiments(unittest.TestCase):
    """ Test the cli tools experiments """

    def test_an_experiment_alias_multi_same_node(self):
        """ Run an experiment """
        nodes = '5,site=devgrenoble+archi=m3:at86rf231'
        cmd = ('experiment-cli submit -d 5 -n test_cli ' +
               '-l {} '.format(nodes) + '-l {}'.format(nodes))

        self._start_experiment(cmd)
        self.assertEquals('Running', self._wait_state_or_finished('Running'))
        time.sleep(1)
        self._get_exp_info()
        self._stop_experiment()
        self._wait_state_or_finished()

    def test_an_experiment_alias_multisite(self):
        """ Run an experiment with multisite/archi """
        call_cli('profile-cli addm3 -n {}'.format('test_m3'))
        call_cli('profile-cli addwsn430 -n {}'.format('test_wsn430'))

        cmd = ('experiment-cli submit -d 5 -n test_cli' +
               (' -l 5,site=devgrenoble+archi=m3:at86rf231,' +
                'integration/m3_autotest.elf,test_m3') +
               (' -l 2,site=devlille+archi=wsn430:cc2420,' +
                'integration/tp.hex,test_wsn430'))

        self._start_experiment(cmd)
        self.assertEquals('Running', self._wait_state_or_finished('Running'))
        time.sleep(1)
        self._get_exp_info()
        self._stop_experiment()
        self._wait_state_or_finished()

    # helpers methods

    def _start_experiment(self, cmd, firmwares=()):
        """ Start an experiment using 'cmd'.
        Add firmwares path to allow checking later """
        LOGGER.info(cmd)
        self.firmwares = firmwares
        self.exp_desc = call_cli(cmd + ' --print')
        self.exp_id = call_cli(cmd, "id")
        self.id_str = ' --id {} '.format(self.exp_id)
        LOGGER.info(self.exp_id)

    def _stop_experiment(self):
        """ Stop current experiment """
        cmd = 'experiment-cli stop -i {}'.format(self.exp_id)
        ret = call_cli(cmd)
        LOGGER.info("%s: %r", cmd, ret['status'])

    def _get_exp_info(self):
        """ Get experiment info and check them """
        cmd = 'experiment-cli get --print' + self.id_str
        exp_json = call_cli(cmd)
        try:
            self.assertNotEquals([], exp_json['deploymentresults']['0'])
        except KeyError:
            LOGGER.warning("No Deploymentresults:%r", exp_json.keys())

        if type(exp_json["nodes"][0]) == dict:
            LOGGER.warning("Nodes are not expanded: %r", exp_json["nodes"])

        cmd = 'experiment-cli get --resources-id -i {}'.format(self.exp_id)
        call_cli(cmd)
        cmd = 'experiment-cli get --resources -i {}'.format(self.exp_id)
        call_cli(cmd)
        call_cli('experiment-cli get -a -i {}'.format(self.exp_id))

    def _wait_state_or_finished(self, state=None):
        """ Wait experiment get in state, or states error and terminated """
        cur_state = None
        states_list = ['Error', 'Terminated']
        states_str = ''
        if state is not None:
            states_list.append(state)
        while True:
            cmd = 'experiment-cli get --exp-state -i {}'.format(self.exp_id)
            state = call_cli(cmd, "state").strip()
            if state != cur_state:
                states_str += state
                print(state, end='')
            states_str += '.'
            print('.', end='')
            sys.stdout.flush()
            cur_state = state
            if state in states_list:
                print('')
                LOGGER.debug(states_str)
                return state
            time.sleep(5)

    # run whole tests only without experiments

    def setUp(self):
        self.cleanup()

    def tearDown(self):
        try:
            os.remove("{}.tar.gz".format(self.exp_id))
        except (OSError, AttributeError):
            pass

    @classmethod
    def tearDownClass(cls):
        cls.cleanup()

    @classmethod
    def cleanup(cls):
        """ Cleanup currently running experiments """
        LOGGER.debug("cleanup")
        cmd = 'experiment-cli get --list --state Running,Waiting'
        experiments = call_cli(cmd, "items")

        for exp in experiments:
            exp_id = exp["id"]
            call_cli('experiment-cli stop -i {}'.format(exp_id))


class TestCliToolsAProfile(unittest.TestCase):
    """ Test the cli tools profile """
    profile = {
        'm3': 'test_cli_profile_m3',
        'm3_full': 'test_cli_profile_m3_full',
        'wsn430': 'test_cli_profile_wsn430',
        'wsn430_full': 'test_cli_profile_wsn430_full',
    }

    @classmethod
    def setUpClass(cls):
        """ Remove the tests profiles if they are here """
        remote_profs = call_cli('profile-cli get --list')
        profiles_names = [p['profilename'] for p in remote_profs]
        for prof in cls.profile.values():
            if prof in profiles_names:
                call_cli('profile-cli del --name {}'.format(prof))

    def _add_profile_simple(self, cmd, name):
        """ Add a profile and get it to check it's the same """
        profile_dict = call_cli(cmd + ' --json')

        # add profile return name
        self.assertEquals(name, call_cli(cmd))

        get_profile_dict = call_cli('profile-cli get --name {}'.format(name))
        # Don't break with new features
        self.assertLessEqual(profile_dict, get_profile_dict)

    def _get_and_load(self, name):
        """ Get a profile and try loading it
        We then check that getting both profiles return the same output
        """

        get_profile_dict = call_cli('profile-cli get --name {}'.format(name))
        with NamedTemporaryFile(mode='w+') as prof:
            prof.write(json.dumps(get_profile_dict))
            prof.flush()
            l_name = call_cli('profile-cli load --file {}'.format(prof.name))
        # returned name are the same
        self.assertEquals(l_name, name)
        get_loaded_profile = call_cli('profile-cli get --name {}'.format(name))
        # returned profile are the same
        self.assertEquals(get_profile_dict, get_loaded_profile)

    def _add_prof(self, cmd, name):
        """ Test adding and loading a user profile """
        self._add_profile_simple(cmd.format(name), name)
        self._get_and_load(name)  # erase same profile

    def test_m3_profile(self):
        """ Test creating M3 profiles and deleting them """

        profs = call_cli('profile-cli get -l')
        profiles_names = set([p['profilename'] for p in profs])

        self._add_prof('profile-cli addm3 -n {}', self.profile['m3'])
        profiles_names.add(self.profile['m3'])

        prof_cmd = 'profile-cli addm3 -n {} -p battery'
        prof_cmd += ' -power -voltage -current -period 8244 -avg 1024'
        prof_cmd += ' -rssi -channels 11 16 21 26 -num 255 -rperiod 65535'
        self._add_prof(prof_cmd, self.profile['m3_full'])
        profiles_names.add(self.profile['m3_full'])

        # check that profiles have been added
        profs = call_cli('profile-cli get -l')
        profiles_names_new = set([p['profilename'] for p in profs])
        self.assertEquals(profiles_names, profiles_names_new)

        # ret == ''
        call_cli('profile-cli del --name {}'.format(self.profile['m3']))
        call_cli('profile-cli del --name {}'.format(self.profile['m3_full']))

    def test_wsn430_profile(self):
        """ Test creating wsn430 profiles and deleting them """

        profs = call_cli('profile-cli get -l')
        profiles_names = set([p['profilename'] for p in profs])

        self._add_prof('profile-cli addwsn430 -n {}', self.profile['wsn430'])
        profiles_names.add(self.profile['wsn430'])

        prof_cmd = 'profile-cli addwsn430 -n {} -p battery'
        prof_cmd += ' -power -voltage -current -cfreq 5000'
        prof_cmd += ' -rfreq 5000'
        prof_cmd += ' -temperature -luminosity -sfreq 30000'
        self._add_prof(prof_cmd, self.profile['wsn430_full'])
        profiles_names.add(self.profile['wsn430_full'])

        # check that profiles have been added
        profs = call_cli('profile-cli get -l')
        profiles_names_new = set([p['profilename'] for p in profs])
        self.assertEquals(profiles_names, profiles_names_new)

        # ret == ''
        call_cli('profile-cli del --name {}'.format(self.profile['wsn430']))
        call_cli('profile-cli del --name {}'.format(
            self.profile['wsn430_full']))


def call_cli(cmd, field=None):
    """ Call cli tool """
    argv = shlex.split(cmd)
    stdout = StringIO()
    with patch('sys.stdout', stdout):
        with patch('sys.argv', argv):
            runpy.run_path(argv[0])
    ret = json.loads(stdout.getvalue())
    if field:
        try:
            ret = ret[field]
        except KeyError as err:
            print(ret, file=sys.stderr)
            raise err

    stdout.close()
    return ret


def setup_auth(username, password):
    """ Setup the username password for test user """
    call_cli('auth-cli --user {} --password {}'.format(username, password))


if __name__ == '__main__':
    USERNAME = "iotlab"
    PASSWORD = os.getenv('IOTLAB_TEST_PASSWORD')
    assert os.getenv('IOTLAB_TEST_PASSWORD') is not None

    os.environ['IOTLAB_PASSWORD_FILE'] = 'test_auth_file'

    setup_auth(USERNAME, PASSWORD)
    unittest.main()

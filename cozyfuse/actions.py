import getpass
import requests
import json
import sys

import couchmount
import replication
import local_config
import remote
import dbutils

from couchdb import Server


def register_device_remotely(name, password):
    '''
    Register device to target Cozy
    '''
    (url, path) = local_config.get_config(name)
    if url[-1:] == '/':
        url = url[:-(len(name)+1)]
    (device_id, device_password) = remote.register_device(name, url,
                                                          path, password)
    local_config.set_device_config(name, device_id, device_password)


def remove_device_remotely(name, password):
    '''
    Delete given device form target Cozy.
    '''
    (url, path) = local_config.get_config(name)
    (device_id, password) = local_config.get_device_config(name)
    remote.remove_device(url, device_id, password)


def init_replication(name):
    '''
    Run initial replications then start continutous replication.
    Write device information in database.
    '''
    (url, path) = local_config.get_config(name)
    (device_id, password) = local_config.get_device_config(name)
    (db_login, db_password) = local_config.get_db_credentials(name)

    print 'Replication from remote to local...'
    replication.replicate(
        name, url, name, password, device_id, db_login, db_password,
        to_local=True, continuous=False, deleted=False)
    print 'Init device...'
    dbutils.init_device(name, url, path, password, device_id)
    print 'Replication from local to remote...'
    replication.replicate(
        name, url, name, password, device_id, db_login, db_password,
        to_local=False, continuous=False)

    print 'Continuous replication from remote to local setting...'
    replication.replicate(name, url, name, password, device_id,
                         db_login, db_password, to_local=True)

    print 'Continuous replication from local to remote setting...'
    replication.replicate(name, url, name, password, device_id,
                          db_login, db_password)
    print 'Metadata replications are done.'

def kill_running_replications():
    '''
    Kill running replications in CouchDB (based on active tasks info).
    Useful when a replication is in Zombie mode.
    '''
    server = Server('http://localhost:5984/')

    for task in server.tasks():
        data = {
            "replication_id": task["replication_id"],
            "cancel": True
        }
        headers = {'content-type': 'application/json'}
        response = requests.post('http://localhost:5984/_replicate',
                                 json.dumps(data), headers=headers)
        if response.status_code == 200:
            print 'Replication %s stopped.' % data['replication_id']
        else:
            print 'Replication %s was not stopped.' % data['replication_id']


def remove_device(name, password):
    '''
    Remove device from local and remote configuration by:

    * Unmounting device folder.
    * Removing device on corresponding remote cozy.
    * Removing device from configuration file.
    * Destroying corresponding DB.
    '''
    (url, path) = local_config.get_config(name)

    couchmount.unmount(path)
    remove_device_remotely(name, password)

    # Remove database
    dbutils.remove_db(name)
    dbutils.remove_db_user(name)

    local_config.remove_config(name)
    print 'Configuration %s successfully removed.' % name


def reset(password):
    '''
    Reset local and remote configuration by:

    * Unmounting each device folder.
    * Removing each device on corresponding remote cozies.
    * Removing configuration file.
    * Destroy corresponding DBs.
    '''
    # Remove devices remotely
    try:
        config = local_config.get_full_config()
    except local_config.NoConfigFile:
        print 'No config file found, cannot reset anything'
        sys.exit(1)

    for name in config.keys():
        print '- Clearing %s' % name
        remove_device(name, password)

    # Remove local config file
    local_config.clear()
    print '[reset] Configuration files deleted, folder unmounted.'


def mount_folder(name):
    '''
    Mount folder linked to given device.
    '''
    try:
        (url, path) = local_config.get_config(name)
        couchmount.unmount(path)
        couchmount.mount(name, path)
    except KeyboardInterrupt:
        unmount_folder(name)


def unmount_folder(name, path=None):
    '''
    Unmount folder linked to given device.
    '''
    if path is None:
        (url, path) = local_config.get_config(name)
    couchmount.unmount(path)


def display_config():
    '''
    Display config file in a human readable way.
    '''
    config = local_config.get_full_config()
    for device in config.keys():
        print 'Configuration for device %s:' % device
        for key in config[device].keys():
            print '    %s = %s' % (key, config[device][key])
        print ' '


def unregister_device(name):
    '''
    Remove device from local configuration, destroy corresponding database
    and unregister it from remote Cozy.
    '''
    (url, path) = local_config.get_config(name)
    (device_id, device_password) = local_config.get_device_config(name)

    print 'Cozy connection removal for %s.' % name
    local_config.remove(name)
    print '- Local configuration removed.'
    dbutils.remove_db(name)
    print '- Local files removed.'
    password = getpass.getpass('Please type the password of your Cozy:\n')
    remote.remove_device(url, device_id, password)
    print '- Remote configuration removed.'
    print 'Removal succeeded, everything clean!' % name


def configure_new_device(name, url, path, password):
    '''
    * Create configuration for given device.
    * Create database and init CouchDB views.
    * Register device on remote Cozy defined by *url*.
    * Init replications.
    '''
    print 'Welcome to Cozy Fuse!'
    print ''
    print 'Let\'s go configuring your new Cozy connection...'
    (db_login, db_password) = dbutils.init_db(name)
    local_config.add_config(name, url, path, db_login, db_password)
    print 'Step 1 succeeded: Local configuration created'
    register_device_remotely(name, password)
    print 'Step 2 succeeded: Device registered remotely.'
    print ''
    print 'Now running the first time replication (it could be very long)...'
    init_replication(name)
    print 'Step 3 succeeded: Metadata copied.'
    print ''
    print 'Cozy configuration %s succeeded!' % name
    print 'Now type cozy-fuse sync-n %s to keep your data synchronized.' % name
    print 'And type cozy-fuse mount -n %s to see your files in your ' \
          'filesystem.' % name


def sync(name):
    '''
    Run continuous synchronization between CouchDB instances.
    '''
    (url, path) = local_config.get_config(name)
    (device_id, device_password) = local_config.get_device_config(name)
    (db_login, db_password) = local_config.get_db_credentials(name)

    replication.replicate(name, url, name, device_password, device_id,
                          db_login, db_password, to_local=True)
    replication.replicate(name, url, name, device_password, device_id,
                          db_login, db_password)

    print 'Continuous replications started.'
    print 'Running daemon for binary synchronization...'
    try:
        context = local_config.get_daemon_context(name, 'sync')
        with context:
            replication.BinaryReplication(name)
    except KeyboardInterrupt:
        print ' Binary Synchronization interrupted.'

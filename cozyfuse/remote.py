import logging
import requests

import local_config

logger = logging.getLogger(__name__)
local_config.configure_logger(logger)


class DeviceAlreadyRegistered(Exception):
    pass


class WrongPassword(Exception):
    pass


class UnreachableCozy(Exception):
    pass


class DeviceNameAlreadyUsed(Exception):
    pass


class WrongCozyURL(Exception):
    pass


def register_device(name, url, path, password):
    '''
    Register device to remote Cozy, located at *url*.
    Once device is registered device id and password are stored in a local
    configuration file.
    '''
    data = {'login': name, 'folder': path}
    try:
        response = requests.post(
            '%s/device/' % url,
            data=data,
            auth=('owner', password),
            verify=False
        )
    except Exception, e:
        msg = '[Remote config] Registering device failed for ' \
              '%s (your Cozy is unreachable).' % name
        print e
        raise WrongCozyURL(msg)
        return

    if response.status_code == 502:
        msg = '[Remote config] Registering device failed for ' \
              '%s (your Cozy is unreachable).' % name
        logger.error(msg)
        raise UnreachableCozy(msg)
    elif response.status_code == 401:
        msg = '[Remote config] Registering device failed for ' \
              '%s (the password doesn\'t match)' % name
        raise WrongPassword(msg)
    elif response.status_code == 400:
        msg = '[Remote config] Registering device failed for ' \
               '%s (this Cozy already has device with this name)' % name
        raise DeviceNameAlreadyUsed(msg)

    data = response.json()
    if ('error' in data):
        msg = '[Remote config] Registering device failed for ' \
              '%s (%s).' % (name, data['error'])
        logger.error(msg)

        if 'name' in msg:
            raise DeviceAlreadyRegistered(msg)
        else:
            raise Exception(msg)

        return (None, None)
    else:
        device_id = str(data["id"])
        device_password = str(data["password"])
        logger.info(
            '[Remote config] Registering device succeeded for %s.' % name)
        return (device_id, device_password)


def remove_device(url, device_id, password):
    '''
    Remove device from its Cozy.
    '''
    response = requests.delete('%s/device/%s/' % (url, device_id),
                    auth=('owner', password), verify=False)

    if response.status_code == 502:
        msg = '[Remote config] Removing device failed ' \
              '(your Cozy is unreachable).'
        logger.error(msg)
        raise UnreachableCozy(msg)
    elif response.status_code == 401:
        msg = '[Remote config] removing device failed ' \
              '(the password doesn\'t match)'
        raise WrongPassword(msg)

    logger.info('[Remote config] Device deletion succeeded for %s.' % url)
    return response

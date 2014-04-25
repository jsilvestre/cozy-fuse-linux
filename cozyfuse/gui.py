import time
from requests import post
from threading import Thread
from multiprocessing import Process
import subprocess

from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.properties import *
from kivy.clock import Clock
from kivy.adapters.listadapter import ListAdapter
from kivy.uix.listview import ListItemButton

import actions
from local_config import LocalDeviceNameAlreadyUsed, get_full_config, get_config
from remote import WrongPassword, UnreachableCozy, DeviceNameAlreadyUsed
from replication import get_progression, get_binary_progression

try:
    import simplejson as json
except ImportError:
    import json  # Python 2.6
import sys

from kivy.uix.listview import ListItemButton

class TabTextInput(TextInput):
    '''
    TabTextInput rewrite TextInput to switch TextInput when user press tab or
    enter
    '''

    def __init__(self, *args, **kwargs):
        self.next = kwargs.pop('next', None)
        super(TabTextInput, self).__init__(*args, **kwargs)

    def set_next(self, next):
        '''
        Initialise next textinput
            next {TextInput}: next textinput on windows
        '''
        self.next = next

    def get_next(self):
        '''
        Return the next TextInput
        '''
        return self.next

    def _keyboard_on_key_down(self, window, keycode, text, modifiers):
        '''
        Catch keyboard events to force a switch between TextInput if necessary
        '''
        key, key_str = keycode
        if key in (9, 13):
            if self.next is not None:
                self.next.focus = True
                self.next.select_all()
        else:
            super(TabTextInput, self)._keyboard_on_key_down(window, keycode,
                                                            text, modifiers)


    def start_sync(self, name):
        sync_thread = Thread(target=actions.sync, args=(name,))
        sync_thread.start()
        print "thread started"


class ConfigurationScreen(Screen):

    def install(self):
        url = self.cozy_url.text
        password = self.cozy_password.text
        name = self.device_name.text
        path = self.local_mount_path.text

        if name is "" or password is "" or url is "":
            self._display_error('All the fields must be filled in')
            return

        url = self._normalize_url(url)
        if not url:
            self._display_error("Your Cozy's URL is not correct")
            return

        self._display_error("Connecting to your Cozy...")

        #Clock.schedule_interval(self.progress_bar, 1/25) # 1/25
        thread_configure = Thread(target=self.configure,
                                  args=(name, url, path, password))
        thread_configure.start()
        thread_configure.join()
        time.sleep(5)
        self.switch_screen()


    def configure(self, name, url, path, password):
        '''
        Configure cozy-files
            name {string}: device name
            url  {string}: cozy url
            path {string}: local folder to mount
            password  {string}: cozy password
        '''

        try:
            actions.configure_new_device(name, url, path, password)
        except WrongPassword, e:
            self._display_error("""The URL and the Cozy's password
                        don't match""")
            return
        except UnreachableCozy, e:
            print e
            self._display_error("""Your Cozy cannot be reached :(
                Are you sure it's up?""")
            return
        except DeviceNameAlreadyUsed, e:
            self._display_error(
                'This device\'s name is already used')
            return
        except LocalDeviceNameAlreadyUsed, e:
            self._display_error("""A config already exist locally
                for this device name""")
            return
        except Exception, e:
            print e
            self._display_error(
                'Your Cozy cannot be reached :(\nAre you connected to internet?')
            return

        self._display_error('Device successfully initialized!')

    def _normalize_url(self, url):
        '''
        Normalize url
            url {string}: cozy url
        '''
        url_parts = url.split('/')
        for part in url_parts:
            if part.find('cozycloud.cc') is not -1:
                return 'https://%s' % part
        return False


    def _display_error(self, error):
        '''
        Display error
            error {string}: message to display
        '''
        self.error_message.text = error
        #self.error.texture_update()


    def switch_screen(self):
        management_screen = sm.get_screen('management')
        management_screen.initialize_data()
        sm.current = 'management'

class ManagementScreen(Screen):

    selected_device = None

    def __init__(self, *args, **kwargs):
        super(ManagementScreen, self).__init__(*args, **kwargs)
        self.initialize_data()

    def initialize_data(self):
        config = get_full_config()


        self.selected_device = None
        self.device_details.opacity = 0.0
        self.device_list.adapter = ListAdapter(data=config.keys(),
                                   cls=ListItemButton)
        self.device_list.adapter.data = config.keys()
        self.device_list.adapter.bind(on_selection_change=self.on_select)


    def on_select(self, list_adapter, *args):
        if len(list_adapter.selection) > 0:
            name = list_adapter.selection[0].text
            self.selected_device = name
            (url, path) = get_config(name)
            self.device_url.text = url
            self.device_mount_path.text = path
            self.device_details.opacity = 1.0

        else:
            self.device_details.opacity = 0.0
            self.selected_device = None

    def on_remove_device(self):
        if self.selected_device is not None:
            popup = Popup()
            def on_confirm_removal(instance):
                try:
                    try:
                        actions.remove_device(self.selected_device, popup.cozy_password.text)
                    except Exception, e:
                        print e
                        popup.feedback_message.text = 'Wrong password'
                        return
                    self.initialize_data()
                    popup.dismiss()
                except Exception, e:
                    popup.feedback_message.text = 'An error occurred while removing the device'
                    print e

            popup.confirm_button.bind(on_press=on_confirm_removal)
            popup.open()

    def on_mount_unmount_device(self):
        print "MOUNT UNMOUNT"


    def on_new_device(self):
        self.selected_device = None
        self.device_details.opacity = 0.0
        sm.current = 'configuration'

Builder.load_file('screen.kv')
Builder.load_file('management.kv')
sm = ScreenManager(transition=FadeTransition())
sm.add_widget(ManagementScreen(name='management'))
sm.add_widget(ConfigurationScreen(name='configuration'))

class ScreenApp(App):

    def build(self):
        return sm

    def on_stop(self):
        print "STOP APPLICATION"


if __name__ == '__main__':
    try:
        ScreenApp().run()
    except KeyboardInterrupt, e:
        print "STOP APPLICATION (keyboard interrupt)"
    except Exception, e:
        print "STOP APPLICATION WITH EXCEPTION"
        print e

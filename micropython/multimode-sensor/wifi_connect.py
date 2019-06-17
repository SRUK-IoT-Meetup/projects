"""
MIT License
Copyright (c) 2019 Samsung. n.herriot@samsung.com
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

__version__ = '0.1.0'
__author__ = 'Nicholas Herriot'
__license__ = "MIT"

import pyb, network, utime, time

class Wifi_manager():
    """
        A pythonic Wifi Manager which will:
        1) Allow you to configure SSID and Password to connect and maintain/check that connection.
        2) Retry and connect if it's been asked to connect and the connection goes down.
        3) Use a WiFi SSID/Password from Flash if it exists.
        4) Encrypt the WiFi SSID/Password on Flash if it does not exist.
        5) Stop a connection and stop the retry/check
        6) Switch to an Access Point mode

        The Wifi manager has internal states for:
        - the current SSID
        - the current password
        - active (i.e. managing a connection )
        - connected
        - last connected local time
    """

    def __init__(self, ssid=None, password=None):
        self.active = False                             # A variable to switch on/off the management of the Wifi connection
        self.connected = False                          # To temporary hold a state of weather we are connected or not. We may remove this.
        self.current_ip_address = None                  # Holds the current IP address.
        self.ssid=ssid
        self.start_time = time.time()                   # The time the Wifi Manager was started
        self._ap_name = None                            # The access point name, if the manager sets up the system as a WiFi Access point
        self._password = password
        self._retries = 3                               # How many retries we try and connect before giving up
        self._timer = None                              # The timer object which handles periodic retries
        self._wifi = network.WLAN()                     # An instance of the network WLAN manager
        print("WiFi Manager bringing up wlan interface.")
        self._wifi.active(1)

    def connect(self, ssid, password):
        """
         Returns True for a successful connection, False for a failed connection.
         The connect method will store:
          - the SSID
          - WiFi Password
          - start a timer to check the connection
          - attempt to retry if it can't connect
          - set state info 'active' and 'connected'

         Retry is controlled by the object attribute called '_retries'. You can set retries with the method set_retries.
         If this is the first time the method has been called, a timer causes the manager to periodically monitor the connection.
         The connect method will return a helpful message to indicate the connection state and IP address.
         The connect method will ensure that the SSID is actually a SSID that is visible and current.
         :return: Boolean, String
         """
        # TODO Refactor and wrap the important function calls in Try/Except caluse
        if ssid is None:
            error = "The WiFi manager needs to know what SSID to connect to. It either has never been configured our you forgot to specify \n " \
                    "e.g. myWifi.connect(ssid='wifi-name', password = 'the-password') "
            return False, error
        self.ssid = ssid

        if password == None:
            error = "The WiFi manager needs to know what password to connect to. It either has never been configured our you forgot to specify \n " \
                    "e.g. myWifi.connect(ssid='wifi-name', password = 'the-password') "
            return False, error
        self._password = password

        # Check the SSID is actually in yor list of SSID's you can see, if not report an error to the caller.
        ssid_values = self._wifi.scan()
        ssid_found = False
        for active_ssid in ssid_values:
            active_ssid = active_ssid[0].decode("utf-8")                # Convert the bstring to a string
            if ssid == active_ssid:
                ssid_found = True
                break
        if not ssid_found:
            return False, "There is no SSID found with the name: {}".format(ssid)

        print("Trying to connect to SSID: {}".format(ssid))
        self._wifi.connect(ssid, password)
        if not self._wifi.isconnected():
            for try_connect in range(self._retries):
                print("Retrying to connect. Trying {} of {}'s".format(try_connect, self._retries))
                self._wifi.connect(ssid, password)
                utime.sleep(3)
                if self._wifi.isconnected():
                    break

        if not self._wifi.isconnected():
            error = "The WiFi connection failed to connect to the SSID {}".format(ssid)
            return False, error

        ip_address = self._wifi.ifconfig()[0]
        self.current_ip_address = ip_address
        message = "IP address is: {}".format(ip_address)

        self.connected = True
        # If this is the first time a connect has been requested then we need to setup the timer to periodically check the connection
        if not self.active:
            print("WiFi Manager is now monitoring the connection")
            self.active = True                                  # Let the WiFi manager store state on managing the WiFi network to true.
            self._timer = pyb.Timer(1, freq=0.1)               # create a timer object using timer 1 - trigger at 0.1Hz
            self._timer.callback(self.__check_connection)         # set the callback to our tick function

        return True, message

    def disconnect(self):
        """
         Disconnects the WLAN connection. This method will check to see if you are connected, then disconnects from the LAN.
         The method also updates all state flags, if a timer is active it will switch  itself off on the next iteration.
         Returns True if successful and provides a message to the caller.
         :return: Boolean, String
         """

        return_value = True
        message = "Wifi connection disconnected"
        try:
            if self._wifi.isconnected():
                self._wifi.disconnect()
            self.connected = False
            self.active = False
            self.current_ip_address = None
        except OSError as error:
            message = "An OS error happened when trying to disconnect. The error was: {}".format(error)
            return_value = False
        except:
            print('Unexpectd error!')
            raise
        return return_value, message

    def __check_connection(self, timer):  # we will receive the timer object when being called
        """
         The private method __check_connection is called by a timer as a callback.
         It's used to check the IP connection and try and reconnect in the event of the connection being pulled down.

         :return:
         """
        # print(timer.counter())              # show current timer's counter value
        if self.active:                     # Check first that we are required to try and reconnect
            if not self._wifi.isconnected():
                self.connected = False
                print("Warning: WiFi connection lost. Trying to reconnect")
                self._wifi.connect(self.ssid, self._password)
            else:
                #print("Connected on IP: {}".format(self.current_ip_address))
                print("Connection up")
                self.connected = True
        else:
            # OK - it looks like we should not be monitoring this connection. Could be a race condition. Make sure we stop monitoring!
            self._timer.deinit()
            print('Wifi Manager has stopped monitoring the connection')

    def retries(self, retry_count=None):
        """
         The retries is used to control how many retries the manager will attempt before giving up.
         It returns True/False and a helpful message in a tuple is the user passes in a valid integer number to retry.
         It returns the current number of retries if no retry value is given.

         :return boolean, string OR int:
         """
        if retry_count is None:
            return self._retries


        return_value = True
        message = None

        try:
            self._retries = 0
            self._retries += retry_count
            if isinstance(self._retries, float):
                self._retries = int(self._retries)
            message = "Retry set to {} retries".format(self._retries)
        except TypeError as error:
            return_value = False
            print(error)
            message = "You must input an integer value to set the number of retries"
            self._retries = 3                   # Reset the retires count back to default TODO make this a config paramter.
        except:
            print("Unexpected error!")
            raise

        return return_value, message

    def set_access_point(self, ap_name="micropython", start_ap=True):
        """
        Set the WLAN to an access point. If the AP name is not given, create a default name of the Wifi LAN connection. Return True if successful or False it
        it fails.
        :param ap_name: A string to name the AP. If it's not set use the default name.
        :return:
        """

        #TODO stop/start AP
        pass

    def status(self):
        """
         The status method is used to pull usefull information about the state of a connection. It returns a status dictionary in the form:
         { Active monitor - If the wifi manager is actively monitoring the connection,
            Connected - If the wifi manager thinks it's connected this will be true.
            Started - A UCL timestamp of when the wifi manager was instantiated
            SSID - The last used wifi hotspot name
            Password - The password used to connect to the SSID
            Retries - The number of retries the wifi manager will attempt when trying to connect
            Current IP address - This will show the current IP if you are connected, or the last IP that you had when connected
            }

         :return dictionary:
         """
        try:
            status = {'Active monitor': self.active,
                           'Connected': self._wifi.isconnected(),
                           'Started': self.start_time,
                           'SSID name': self.ssid,
                           'Password': self._password,          # TODO Think about encrypting this and storing on SD card
                           'Retries': self._retries,
                           'Current IP address': self._wifi.ifconfig()[0]
                           }
            return_value = True
        except OSError as error:
            status = "An OS error happened when trying to get status information. Please try again. The error was: {}".format(error)
            return_value = False
        except:
            print('Unexpectd error!')
            raise

        return return_value, status

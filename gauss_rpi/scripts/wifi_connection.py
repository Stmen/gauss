#!/usr/bin/env python

# Copyright (C) 2017 Niryo
# All rights reserved.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import rospy
from threading import Thread

from std_msgs.msg import Bool

from gauss_msgs.srv import SetInt

from gauss_rpi.wifi.robot_name_handler import *
from gauss_rpi.wifi.broadcast import *
from gauss_rpi.wifi import flask_app as app
from gauss_rpi.wifi.flask_views import set_hotspot_ssid
from gauss_rpi.wifi.flask_views import set_hotspot_password
import gauss_rpi.wifi.network_manager as gauss_wifi

class WifiConnectionManager:

    def send_hotspot_state(self, event):
        activated = gauss_wifi.is_hotspot_activated() # would be better to call get_current_ssid, but takes 0.3 sec
        self.publish_hotspot_state(activated)

    def publish_hotspot_state(self, activated):
        msg = Bool()
        msg.data = activated
        self.hotspot_state_publisher.publish(msg)
    
    def service_response(self, status, message):
        return {'status': status, 'message': message}

    def callback_activate_hotspot(self, req):
        rospy.loginfo("Switch to hotspot mode")
        if gauss_wifi.get_current_ssid() == self.hotspot_ssid:
            return self.service_response(200, "Hotspot mode already activated")
        success = gauss_wifi.hard_enable_hotspot_with_ssid(self.hotspot_ssid, self.hotspot_password)
        if success:
            return self.service_response(200, "Hotspot mode activated")
        return self.service_response(400, "Failed to activate hotspot mode")

    def start_broadcast(self):
        start_broadcast_ip_publisher()
    
    def run_flask_server(self):
        app.run(host='0.0.0.0')

    def get_robot_unique_identifier(self):
        identifier = ''
        with open('/proc/cpuinfo', 'r') as f:
            rpi_serial = ''
            for line in f:
                if line[0:6] == 'Serial':
                    rpi_serial = line[10:26]
                    break
            if rpi_serial != '':
                # Build something readable and not too long
                identifier = str(rpi_serial[8:10]) + '-' + str(rpi_serial[10:13]) + '-' + str(rpi_serial[13:16])
        return identifier

    def __init__(self):
        rospy.loginfo("Starting wifi manager...")
        
        self.hotspot_ssid = rospy.get_param("~hotspot_ssid")
        # add robot unique identifier to ssid to make it unique and recognizable
        self.hotspot_ssid += " "
        self.hotspot_ssid += str(self.get_robot_unique_identifier()) 
        self.hotspot_password = rospy.get_param("~hotspot_password")
        self.filename_robot_name = rospy.get_param("~filename_robot_name")

        # Set filename for robot name
        set_filename_robot_name(self.filename_robot_name)

        # Set Gauss hotspot ssid and password
        set_hotspot_ssid(self.hotspot_ssid)
        set_hotspot_password(self.hotspot_password)

        # Start broadcast
        broadcast_thread = Thread(target=self.start_broadcast)
        broadcast_thread.setDaemon(True)
        broadcast_thread.start()

        # Check if connected to Wi-Fi. If not, start hotspot mode
        current_ssid = gauss_wifi.get_current_ssid()
        rospy.loginfo("Current ssid : " + str(current_ssid))
        if not gauss_wifi.is_connected_to_wifi():
            gauss_wifi.hard_enable_hotspot_with_ssid(self.hotspot_ssid, self.hotspot_password)
        else:
            rospy.loginfo("Already connected to a Wifi or in Hotspot mode")

        # Start Flask app
        flask_thread = Thread(target=self.run_flask_server)
        flask_thread.setDaemon(True)
        flask_thread.start()

        # Start wifi status publisher
        self.hotspot_state_publisher = rospy.Publisher('/gauss/wifi/hotspot', Bool, queue_size=2)
        rospy.Timer(rospy.Duration(1), self.send_hotspot_state)

        # Start hotspot subscriber (from button)
        self.activate_hotspot_server = rospy.Service('/gauss/wifi/set_hotspot', 
                SetInt, self.callback_activate_hotspot)
        
        rospy.loginfo("Wifi manager started")


if __name__ == '__main__':
    #rospy.init_node('gauss_wifi_connection_manager')
    #WifiConnectionManager()
    #rospy.spin()
    pass

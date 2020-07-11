#!/usr/bin/env python
# -*- coding: utf-8 -*-
# BEGIN LICENSE
# Copyright (c) 2014 Jim Kemp <kemp.jim@gmail.com>
# Copyright (c) 2017 Gene Liverman <gene@technicalissues.us>

# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
# END LICENSE

""" Fetches weather reports from Dark Sky for displaying on a screen. """

__version__ = "0.0.2"

###############################################################################
#   Raspberry Pi & Lichee Zero Pi: Calendar and Weather Display
#   Original By: Jim Kemp          10/25/2014
#   Modified By: Gene Liverman    12/30/2017 & multiple times since
#   Mooified By: Daniel C.        10/06/2020
###############################################################################
# standard imports
import datetime
import os
import platform
import signal
import sys
import syslog
import time
import calendar
import schedule

#Localization imports
import locale
from strings_defs import * # strings dictionary

# third party imports
from darksky import forecast
import pygame
# from pygame.locals import *
import requests

# local imports
import config

# google calendar imports
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
# If modifying these scopes, delete the file token.pickle
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# setup GPIO pin
#import LPi.GPIO as GPIO
#GPIO.setmode( GPIO.BOARD )
#GPIO.setup( 6, GPIO.IN )    # Next 
##GPIO.setup( 17, GPIO.IN, pull_up_down=GPIO.PUD_DOWN )    # Shutdown

# globals
MODE = 'd'  # Default to weather mode.
MOUSE_X, MOUSE_Y = 0, 0
UNICODE_DEGREE = u'\xb0'

if config.LANG == 'es':
    locale.setlocale(locale.LC_ALL, 'es_ES.UTF-8') # this set date and time in local format

def exit_gracefully(signum, frame):
    sys.exit(0)


signal.signal(signal.SIGTERM, exit_gracefully)


def deg_to_compass(degrees):
    val = int((degrees/22.5)+.5)
    dirs = ["N", "NNE", "NE", "ENE",
            "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW",
            "W", "WNW", "NW", "NNW"]
    return dirs[(val % 16)]


def units_decoder(units):
    """
    https://darksky.net/dev/docs has lists out what each
    unit is. The method below is just a codified version
    of what is on that page.
    """
    si_dict = {
        'nearestStormDistance': 'Kilometers',
        'precipIntensity': 'Millimeters per hour',
        'precipIntensityMax': 'Millimeters per hour',
        'precipAccumulation': 'Centimeters',
        'temperature': 'Degrees Celsius',
        'temperatureMin': 'Degrees Celsius',
        'temperatureMax': 'Degrees Celsius',
        'apparentTemperature': 'Degrees Celsius',
        'dewPoint': 'Degrees Celsius',
        'windSpeed': 'Meters per second',
        'windGust': 'Meters per second',
        'pressure': 'Hectopascals',
        'visibility': 'Kilometers',
    }
    ca_dict = si_dict.copy()
    ca_dict['windSpeed'] = 'Kilometers per hour'
    ca_dict['windGust'] = 'Kilometers per hour'
    uk2_dict = si_dict.copy()
    uk2_dict['nearestStormDistance'] = 'Miles'
    uk2_dict['visibility'] = 'Miles'
    uk2_dict['windSpeed'] = 'Miles per hour'
    uk2_dict['windGust'] = 'Miles per hour'
    us_dict = {
        'nearestStormDistance': 'Miles',
        'precipIntensity': 'Inches per hour',
        'precipIntensityMax': 'Inches per hour',
        'precipAccumulation': 'Inches',
        'temperature': 'Degrees Fahrenheit',
        'temperatureMin': 'Degrees Fahrenheit',
        'temperatureMax': 'Degrees Fahrenheit',
        'apparentTemperature': 'Degrees Fahrenheit',
        'dewPoint': 'Degrees Fahrenheit',
        'windSpeed': 'Miles per hour',
        'windGust': 'Miles per hour',
        'pressure': 'Millibars',
        'visibility': 'Miles',
    }
    switcher = {
        'ca': ca_dict,
        'uk2': uk2_dict,
        'us': us_dict,
        'si': si_dict,
    }
    return switcher.get(units, "Invalid unit name")


def get_abbreviation(phrase):
    abbreviation = ''.join(item[0].lower() for item in phrase.split())
    return abbreviation


def get_windspeed_abbreviation(unit=config.UNITS):
    return get_abbreviation(units_decoder(unit)['windSpeed'])


def get_temperature_letter(unit=config.UNITS):
    return units_decoder(unit)['temperature'].split(' ')[-1][0].upper()



def icon_mapping(icon, size):
    """
    https://darksky.net/dev/docs has this to say about icons:
    icon optional
    A machine-readable text summary of this data point, suitable for selecting an
    icon for display. If defined, this property will have one of the following
    values: clear-day, clear-night, rain, snow, sleet, wind, fog, cloudy,
    partly-cloudy-day, or partly-cloudy-night. (Developers should ensure that a
    sensible default is defined, as additional values, such as hail, thunderstorm,
    or tornado, may be defined in the future.)

    Based on that, this method will map the Dark Sky icon name to the name of an
    icon in this project.
    """
    if icon == 'clear-day':
        icon_path = 'icons/{}/clear.png'.format(size)
    elif icon == 'clear-night':
        icon_path = 'icons/{}/nt_clear.png'.format(size)
    elif icon == 'rain':
        icon_path = 'icons/{}/rain.png'.format(size)
    elif icon == 'snow':
        icon_path = 'icons/{}/snow.png'.format(size)
    elif icon == 'sleet':
        icon_path = 'icons/{}/sleet.png'.format(size)
    elif icon == 'wind':
        icon_path = 'icons/alt_icons/{}/wind.png'.format(size)
    elif icon == 'fog':
        icon_path = 'icons/{}/fog.png'.format(size)
    elif icon == 'cloudy':
        icon_path = 'icons/{}/cloudy.png'.format(size)
    elif icon == 'partly-cloudy-day':
        icon_path = 'icons/{}/partlycloudy.png'.format(size)
    elif icon == 'partly-cloudy-night':
        icon_path = 'icons/{}/nt_partlycloudy.png'.format(size)
    else:
        icon_path = 'icons/{}/unknown.png'.format(size)

    # print(icon_path)
    return icon_path


# Helper function to which takes seconds and returns (hours, minutes).
# ###########################################################################
def stot(sec):
    mins = sec.seconds // 60
    hrs = mins // 60
    return (hrs, mins % 60)


###############################################################################
class MyDisplay:
    screen = None

    ####################################################################
    def __init__(self):
        "Ininitializes a new pygame screen using the framebuffer"
        if platform.system() == 'Darwin':
            pygame.display.init()
            driver = pygame.display.get_driver()
            print('Using the {0} driver.'.format(driver))
        else:
            # Based on "Python GUI in Linux frame buffer"
            # http://www.karoltomala.com/blog/?p=679
            disp_no = os.getenv("DISPLAY")
            if disp_no:
                print("X Display = {0}".format(disp_no))
                syslog.syslog("X Display = {0}".format(disp_no))

            # Check which frame buffer drivers are available
            # Start with fbcon since directfb hangs with composite output
            drivers = ['x11', 'fbcon', 'directfb', 'svgalib']
            found = False
            for driver in drivers:
                # Make sure that SDL_VIDEODRIVER is set
                if not os.getenv('SDL_VIDEODRIVER'):
                    os.putenv('SDL_VIDEODRIVER', driver)
                try:
                    pygame.display.init()
                except pygame.error:
                    print('Driver: {0} failed.'.format(driver))
                    syslog.syslog('Driver: {0} failed.'.format(driver))
                    continue
                found = True
                break

            if not found:
                raise Exception('No suitable video driver found!')

        size = (pygame.display.Info().current_w,
                pygame.display.Info().current_h)
        print("Framebuffer Size: %d x %d" % (size[0], size[1]))
        syslog.syslog("Framebuffer Size: %d x %d" % (size[0], size[1]))
        self.screen = pygame.display.set_mode(size, pygame.FULLSCREEN)
        # Clear the screen to start
        self.screen.fill((0, 0, 0))
        # Initialise font support
        pygame.font.init()
        # Render the screen
        pygame.mouse.set_visible(0)
        pygame.display.update()
        # Print out all available fonts
        # for fontname in pygame.font.get_fonts():
        #        print(fontname)

        if config.FULLSCREEN:
            self.xmax = pygame.display.Info().current_w #- 35
            self.ymax = pygame.display.Info().current_h #- 5
            if self.xmax <= 1024:
                self.icon_size = '64'
            else:
                self.icon_size = '256'
        else:
            self.xmax = 480 - 35
            self.ymax = 320 - 5
            self.icon_size = '64'
        self.subwindow_text_height = 0.055
        self.time_text_height = 0.30       #0.115
        self.time_seconds_text_height = 0.15
        self.date_text_height =  0.075
        self.window_division_x = 0.72       # screen vertical division between calendar and weather from left
        self.time_y_position = -3
        self.time_seconds_y_position = 12
        self.eventsdate = [ '', '', '', '', '' ]
        self.eventstime = [ '', '', '', '', '' ]
        self.eventsdesc = [ '', '', '', '', '' ]
        self.last_update_check = 0

    def __del__(self):
        "Destructor to make sure pygame shuts down, etc."
    
    ####################################################################
    def get_calendar_events( self ):

        todaydate = datetime.datetime(2017,1,1,0,0)
        datetimetmp = datetime.datetime(2017,1,1,0,0)

        """Shows basic usage of the Google Calendar API.
        Prints the start and name of the next 10 events on the user's calendar.
        """
        creds = None
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        service = build('calendar', 'v3', credentials=creds)

        now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
        try:
            eventsResult = service.events().list(
                calendarId='primary', timeMin=now, maxResults=4, singleEvents=True,
                orderBy='startTime').execute()
        except:
            print("Error getting events from Google Calendar")
            return
        events = eventsResult.get('items', [])
        
        if not events:
            print("No upcoming events found.")
        i=0
        todaydate = datetime.datetime.today().replace(hour=0, minute=0, second=0, microsecond=0) 
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            if len(start) > 10:
                start = start[:start.find("+")]
                datetimetmp = datetime.datetime.strptime(start, "%Y-%m-%dT%H:%M:%S")
                self.eventstime[i] = datetime.datetime.strftime(datetimetmp, "%H:%M")
            else:
                datetimetmp = datetime.datetime.strptime(start, "%Y-%m-%d")
                self.eventstime[i] = ""
            if ( datetimetmp.replace(hour=0, minute=0) == todaydate ):
                self.eventsdate[i] = gettext('TODAY', lang)
            elif ( datetimetmp.replace(hour=0, minute=0) == ( todaydate + datetime.timedelta(days=1))):
                self.eventsdate[i] = gettext('TOMORROW', lang)
            else:
                self.eventsdate[i] = datetime.datetime.strftime(datetimetmp, "%A, %d %B").title()
            self.eventsdesc[i] = event['summary']
            i+=1
        return True

    def get_forecast(self):
        if (time.time() - self.last_update_check) > config.DS_CHECK_INTERVAL:
            self.last_update_check = time.time()
            try:
                self.weather = forecast(config.DS_API_KEY,
                                        config.LAT,
                                        config.LON,
                                        exclude='minutely',
                                        units=config.UNITS,
                                        lang=config.LANG)

                sunset_today = datetime.datetime.fromtimestamp(
                    self.weather.daily[0].sunsetTime)
                if datetime.datetime.now() < sunset_today:
                    index = 0
                    sr_suffix = 'today'
                    ss_suffix = 'tonight'
                else:
                    index = 1
                    sr_suffix = 'tomorrow'
                    ss_suffix = 'tomorrow'

                self.sunrise = self.weather.daily[index].sunriseTime
                self.sunrise_string = datetime.datetime.fromtimestamp(
                    self.sunrise).strftime("%I:%M %p {}").format(sr_suffix)
                self.sunset = self.weather.daily[index].sunsetTime
                self.sunset_string = datetime.datetime.fromtimestamp(
                    self.sunset).strftime("%I:%M %p {}").format(ss_suffix)

                # start with saying we don't need an umbrella
                self.take_umbrella = False
                icon_now = self.weather.icon
                icon_today = self.weather.daily[0].icon
                if icon_now == 'rain' or icon_today == 'rain':
                    self.take_umbrella = True
                else:
                    # determine if an umbrella is needed during daylight hours
                    curr_date = datetime.datetime.today().date()
                    for hour in self.weather.hourly:
                        hr = datetime.datetime.fromtimestamp(hour.time)
                        sr = datetime.datetime.fromtimestamp(
                            self.weather.daily[0].sunriseTime)
                        ss = datetime.datetime.fromtimestamp(
                            self.weather.daily[0].sunsetTime)
                        rain_chance = hour.precipProbability
                        is_today = hr.date() == curr_date
                        is_daylight_hr = hr >= sr and hr <= ss
                        if is_today and is_daylight_hr and rain_chance >= .25:
                            self.take_umbrella = True
                            break

            except requests.exceptions.RequestException as e:
                print('Request exception: ' + str(e))
                return False
            except AttributeError as e:
                print('Attribute error: ' + str(e))
                return False
        return True

    def display_conditions_line(self, label, cond, is_temp, multiplier=None):
        y_start_position = 0     #start position
        line_spacing_gap = 0.065    #line spacing
        conditions_text_height = 0.04
        x_start_position = self.xmax 
        text_color = (255, 255, 255)
        font_name = "freesans"

        y_start = (y_start_position + line_spacing_gap * multiplier)

        conditions_font = pygame.font.SysFont(
            font_name, int(self.ymax * conditions_text_height), bold=0)

        txt_label = conditions_font.render(str(label), True, text_color)
        (txt_label_x, txt_label_y) = txt_label.get_size()


        txt_cond = conditions_font.render(str(cond), True, text_color)
        (txt_cond_x, txt_cond_y) = txt_cond.get_size()
        self.screen.blit(txt_label, 
            ( x_start_position-txt_label_x - txt_cond_x - 10, self.ymax * y_start + txt_label_y + 4))

        self.screen.blit(txt_cond, 
            ( x_start_position- txt_cond_x , self.ymax * y_start + txt_label_y + 4))


    def display_subwindow(self, data, day, c_times):
        subwindow_centers = 0.125
        subwindows_y_start_position = 0.250 + 0.1875/2  # Sub windows Y axis center
        line_spacing_gap = 0.1875                  # Vertical spacing between Windows
        rain_present_text_height = 0.060
        text_color = (255, 255, 255)
        font_name = "freesans"

        subwindow_y_center_pos = subwindows_y_start_position + c_times * line_spacing_gap
        subwindow_y_upper_pos = subwindow_y_center_pos - line_spacing_gap /2
        subwindow_y_lower_pos = subwindow_y_center_pos + line_spacing_gap /2 - 0.03125

        # Day of week or time
        forecast_font = pygame.font.SysFont(
            font_name, int(self.ymax * self.subwindow_text_height), bold=0)
        rpfont = pygame.font.SysFont(
            font_name, int(self.ymax * rain_present_text_height), bold=0)
        day_hour_temp_font = pygame.font.SysFont(
            font_name, int(self.ymax * self.subwindow_text_height*1.3), bold=0)
        degree_font = pygame.font.SysFont(
            font_name, int(self.ymax * self.subwindow_text_height * 1.3* 0.5), bold=0)
        
        dayhour_txt = forecast_font.render(day, True, text_color)
        (rendered_dayhour_txt_x, rendered_dayhour_txt_y) = dayhour_txt.get_size()
        #Display day
        self.screen.blit(dayhour_txt, (self.xmax * self.window_division_x,
                               self.ymax * subwindow_y_center_pos - rendered_dayhour_txt_y/2))
        degree_txt = degree_font.render(UNICODE_DEGREE+get_temperature_letter(), True, text_color)
        (rendered_degree_x, rendered_degree_y) = degree_txt.get_size()

        # Display day temp or hour temp
        if hasattr(data, 'temperatureLow'):
            temp_txt = day_hour_temp_font.render(
                str(int(round(data.temperatureHigh))), True, text_color)
            temp_low = day_hour_temp_font.render(
                str(int(round(data.temperatureLow))), True, text_color)
            (rendered_temp_txt_x, rendered_temp_txt_y) = temp_txt.get_size()
            (rendered_temp_low_x, rendered_temp_low_y) = temp_low.get_size()
            self.screen.blit(temp_txt, (self.xmax - rendered_temp_txt_x - rendered_degree_x ,
                                   self.ymax * subwindow_y_upper_pos + rendered_temp_txt_y * 0.2 ))
            self.screen.blit(degree_txt, (self.xmax - rendered_degree_x * 1.1 ,
                                   self.ymax * subwindow_y_upper_pos + rendered_temp_txt_y * 0.2 +4 ))  
            self.screen.blit(temp_low, (self.xmax - rendered_temp_low_x - rendered_degree_x ,
                                   self.ymax * subwindow_y_lower_pos - rendered_temp_low_y * 0.5 ))
            self.screen.blit(degree_txt, (self.xmax - rendered_degree_x * 1.1 ,
                                   self.ymax * subwindow_y_lower_pos - rendered_temp_low_y * 0.5 +4)) 
        else:
            rendered_temp_low_x = 0
            temp_txt = day_hour_temp_font.render(
                str(int(round(data.temperature))), True, text_color)
            (rendered_temp_txt_x, rendered_temp_txt_y) = temp_txt.get_size()
            self.screen.blit(temp_txt, (self.xmax - rendered_temp_txt_x - rendered_degree_x ,
                                   self.ymax * subwindow_y_center_pos - rendered_temp_txt_y /2 ))
            self.screen.blit(degree_txt, (self.xmax - rendered_degree_x * 1.1 ,
                                   self.ymax * subwindow_y_center_pos - rendered_temp_txt_y /2 +4 )) 

        # rtxt = forecast_font.render('Rain:', True, lc)
        # self.screen.blit(rtxt, (ro,self.ymax*(wy+gp*5)))
        rptxt = rpfont.render(
            str(int(round(data.precipProbability * 100))) + '%',
            True, text_color)
        (txt_x, txt_y) = rptxt.get_size()
        self.screen.blit(rptxt, (self.xmax * self.window_division_x + 4 ,
                                self.ymax * subwindow_y_lower_pos - txt_y/2 ))
        icon = pygame.image.load(
            icon_mapping(data.icon, self.icon_size)).convert_alpha()
        (icon_size_x, icon_size_y) = icon.get_size()
        if icon_size_y < 90:
            icon_y_offset = (90 - icon_size_y) / 2
        else:
            icon_y_offset = config.LARGE_ICON_OFFSET

        self.screen.blit(icon, ((self.xmax * (self.window_division_x + 1) + rendered_dayhour_txt_x 
                                - max(rendered_temp_txt_x, rendered_temp_low_x) - rendered_degree_x)/2
                                - icon_size_x/2 - 2, self.ymax * subwindow_y_center_pos - icon_size_y /2 ))

    def disp_summary(self):
        y_start_position =  0.25 + 0.1875
        conditions_text_height = 0.04
        text_color = (255, 255, 255)
        font_name = "freesans"

        conditions_font = pygame.font.SysFont(
            font_name, int(self.ymax * conditions_text_height), bold=0)
        txt = conditions_font.render(self.weather.summary, True, text_color)
        (rendered_txt_x, rendered_txt_y) = txt.get_size()
        x = self.xmax * self.window_division_x * 1.01 #= self.xmax * (self.window_division_x + 1 ) /2 - (rendered_txt_x * 1.50 ) / 2
        y = ( self.ymax * y_start_position - rendered_txt_y * 1.50) / 2
        self.screen.blit(txt, (x, y))

    def disp_umbrella_info(self, umbrella_txt):
        x_start_position = 0.52
        y_start_position = 0.444
        conditions_text_height = 0.04
        text_color = (255, 255, 255)
        font_name = "freesans"

        conditions_font = pygame.font.SysFont(
            font_name, int(self.ymax * conditions_text_height), bold=1)
        txt = conditions_font.render(umbrella_txt, True, text_color)
        self.screen.blit(txt, (
            self.xmax * x_start_position,
            self.ymax * y_start_position))

    def disp_calendar_events(self):
        font_name = "freesans"
        #Google calendar events
        dfont = pygame.font.SysFont( font_name, int(self.ymax*self.date_text_height*1.1), bold=0 ) # Date Font 
        dsfont = pygame.font.SysFont( font_name, int(self.ymax*self.date_text_height*1.1), bold=0 ) # Date Font 
        gcy = self.ymax * 0.45
        gpy = 24    #gap on axis y, between event date/time line and event description
        gpx = 15    #gap on axis x, between Date and time
        tp = 4
        lcdt = (230,230,230)
        lctm = (255, 204, 255)
        text_color = (255, 255, 255)

        for i in range(3):
            if ( self.eventsdate[i]==gettext('TODAY', config.LANG)):
                lcdt = (204, 255, 204)
            elif (self.eventsdate[i]==gettext('TOMORROW', config.LANG)):
                lcdt = (255, 255, 204)
            else:
                lcdt = (230, 230, 230)
            gedate = dfont.render(  self.eventsdate[i] , True, lcdt )
            (gdx,gdy) = gedate.get_size()
            self.screen.blit( gedate, (tp, gcy-gpy ) ) #event date
            getime = dfont.render( self.eventstime[i] , True, lctm )
            (gtx,gty) = getime.get_size()
            self.screen.blit( getime, (tp+gdx+gpx, gcy-gpy  ) ) #event hours
            gcy = gcy + gdy-4
            gedesc = dsfont.render ( self.eventsdesc[i] ,  True, text_color )
            (gdsx, gdsy) = gedesc.get_size()
            while ( gdsx > self.xmax * self.window_division_x):
                self.eventsdesc[i] = self.eventsdesc[i][:-1]
                gedesc = dsfont.render ( self.eventsdesc[i] ,  True, text_color )
                (gdsx, gdsy) = gedesc.get_size()
            self.screen.blit( gedesc, (tp, gcy-gpy )) #event description
            gcy = gcy + gty + 15


    def disp_weather(self):
        # Fill the screen with black
        self.screen.fill((0, 0, 0))
        xmin = self.window_division_x
        lines = 2
        line_color = (255, 255, 255)
        text_color = (255, 255, 255)
        font_name = "freesans"

        self.draw_screen_border(line_color, xmin, lines)
        self.disp_time_date(font_name, text_color)
        self.disp_current_temp(font_name, text_color)
        self.disp_summary()

        try:
            wind_bearing = self.weather.windBearing
            wind_direction = deg_to_compass(wind_bearing) + ' @ '
        except AttributeError:
            wind_direction = ''
        self.display_conditions_line(
            'HR:', str(int(round((self.weather.humidity * 100)))) + '%',
            False, 0)        
        wind_txt = wind_direction + str(
            int(round(self.weather.windSpeed))) + \
            ' ' + get_windspeed_abbreviation()
        self.display_conditions_line(
            '', wind_txt, False, 2.4)

        # Skipping multiplier 3 (line 4)

        if self.take_umbrella:
            umbrella_txt = 'Grab your umbrella!'
        else:
            umbrella_txt = 'No umbrella needed today.'
        self.disp_umbrella_info(umbrella_txt)

        # Today
        today = self.weather.daily[0]
        today_string = "Today"
        multiplier = 0
        self.display_subwindow(today, today_string, multiplier)

        # counts from 0 to 2
        for future_day in range(3):
            this_day = self.weather.daily[future_day + 1]
            this_day_no = datetime.datetime.fromtimestamp(this_day.time)
            this_day_string = this_day_no.strftime("%A")
            multiplier += 1
            self.display_subwindow(this_day, this_day_string, multiplier)

        # Update the display
        pygame.display.update()

    def disp_hourly(self):
        # Fill the screen with black
        self.screen.fill((0, 0, 0))
        xmin = self.window_division_x
        lines = 2
        line_color = (255, 255, 255)
        text_color = (255, 255, 255)
        font_name = "freesans"

        self.draw_screen_border(line_color, xmin, lines)
        self.disp_time_date(font_name, text_color)
        self.disp_current_temp(font_name, text_color)
        self.disp_summary()
        #self.display_conditions_line(
        #    'Feels Like:', int(round(self.weather.apparentTemperature)),
        #    True)

        try:
            wind_bearing = self.weather.windBearing
            wind_direction = deg_to_compass(wind_bearing) + ' @ '
        except AttributeError:
            wind_direction = ''
        wind_txt = wind_direction + str(
            int(round(self.weather.windSpeed))) + \
            ' ' + get_windspeed_abbreviation()
        self.display_conditions_line(
            'Wind:', wind_txt, False, 1)

        self.display_conditions_line(
            'Humidity:', str(int(round((self.weather.humidity * 100)))) + '%',
            False, 2)

        # Skipping multiplier 3 (line 4)

        if self.take_umbrella:
            umbrella_txt = 'Grab your umbrella!'
        else:
            umbrella_txt = 'No umbrella needed today.'
        self.disp_umbrella_info(umbrella_txt)

        # Current hour
        this_hour = self.weather.hourly[0]
        this_hour_24_int = int(datetime.datetime.fromtimestamp(
            this_hour.time).strftime("%H"))
        if this_hour_24_int <= 11:
            ampm = 'a.m.'
        else:
            ampm = 'p.m.'
        this_hour_12_int = int(datetime.datetime.fromtimestamp(
            this_hour.time).strftime("%I"))
        this_hour_string = "{} {}".format(str(this_hour_12_int), ampm)
        multiplier = 0
        self.display_subwindow(this_hour, this_hour_string, multiplier)

        # counts from 0 to 2
        for future_hour in range(3):
            this_hour = self.weather.hourly[future_hour + 1]
            this_hour_24_int = int(datetime.datetime.fromtimestamp(
                this_hour.time).strftime("%H"))
            if this_hour_24_int <= 11:
                ampm = 'a.m.'
            else:
                ampm = 'p.m.'
            this_hour_12_int = int(datetime.datetime.fromtimestamp(
                this_hour.time).strftime("%I"))
            this_hour_string = "{} {}".format(str(this_hour_12_int), ampm)
            multiplier += 1
            self.display_subwindow(this_hour, this_hour_string, multiplier)

        # Update the display
        pygame.display.update()

    def disp_current_temp(self, font_name, text_color):
        # Outside Temp
        outside_temp_font = pygame.font.SysFont(
            font_name, int(self.ymax * (0.2125)), bold=0)
        temp_txt = outside_temp_font.render(
            str(int(round(self.weather.temperature))), True, text_color)
        (rendered_temp_txt_x, rendered_temp_txt_y) = temp_txt.get_size()
        degree_font = pygame.font.SysFont(
            font_name, int(self.ymax * (0.2125) * 0.5), bold=0)
        degree_txt = degree_font.render(UNICODE_DEGREE, True, text_color)
        (rendered_degree_x, rendered_degree_y) = degree_txt.get_size()
        degree_letter = degree_font.render(get_temperature_letter(),
                                                 True, text_color)
        (rendered_dletter_x, rendered_dletter_y) = degree_letter.get_size()
        
        # Position text
        x = self.xmax * self.window_division_x  #=self.xmax * (self.window_division_x + 1 ) /2 - (rendered_temp_txt_x * 0.95
        #     + rendered_degree_x * 0.70 + rendered_dletter_x) / 2
        y = ( self.ymax *  0.25 - rendered_temp_txt_y - 24) / 2
        self.screen.blit(temp_txt, (x, y ))
        x = x + (rendered_temp_txt_x * 0.95)
        self.screen.blit(degree_txt, (x, y + 12))
        x = x + (rendered_degree_x * 0.70)
        self.screen.blit(degree_letter, (x, y + 12))

    def disp_time_date(self, font_name, text_color):
        # Time & Date
        time_font = pygame.font.SysFont(
            font_name, int(self.ymax * self.time_text_height), bold=0)
        # Small Font for Seconds
        time_seconds_font = pygame.font.SysFont(
            font_name, int(self.ymax * self.time_seconds_text_height), bold=0)
        # Small Font for Date
        date_font = pygame.font.SysFont(
            font_name, int(self.ymax * self.date_text_height), bold=0)

        time_string = time.strftime("%H:%M", time.localtime())
        secs_string = time.strftime("%S", time.localtime())
        date_string = time.strftime("%A, %d %B", time.localtime()).title()

        rendered_time_string = time_font.render(time_string, True,
                                                     text_color)
        (rendered_time_x, rendered_time_y) = rendered_time_string.get_size()
        rendered_secs_string = time_seconds_font.render(secs_string, True,
                                                  text_color)
        (rendered_secs_x, rendered_secs_y) = rendered_secs_string.get_size()
        rendered_date_string = date_font.render(date_string, True,
                                                   text_color)
        (rendered_date_x, rendered_date_y) = rendered_date_string.get_size()

        full_time_string_x_position = ( self.xmax * self.window_division_x ) / 2 - (rendered_time_x+ 2*rendered_secs_y/1.4) / 2
        self.screen.blit(rendered_time_string, (full_time_string_x_position,
                                                self.time_y_position))
        self.screen.blit(rendered_secs_string,
                         (full_time_string_x_position + rendered_time_x + 3,
                          self.time_seconds_y_position))
        full_date_string_x_position = self.xmax * self.window_division_x / 2 - rendered_date_x / 2
        self.screen.blit(rendered_date_string,
                         (full_date_string_x_position, rendered_time_y -15) )

    def draw_screen_border(self, line_color, xmin, lines):
        # Draw Screen Border
        # Draw Weather Forecast Sub divisions: height 25% | 75%/4 | 75%/4 | 75%/4 | 75%/4
        pygame.draw.line( self.screen, line_color, (self.xmax*xmin,self.ymax*0.25),
                            (self.xmax,self.ymax*0.25), lines )        # Temp Window 25% height
        pygame.draw.line( self.screen, line_color, (self.xmax*xmin,self.ymax*0.4375),
                            (self.xmax,self.ymax*0.4375), lines )    # 1st W Forecast
        pygame.draw.line( self.screen, line_color, (self.xmax*xmin,self.ymax*0.6250),
                            (self.xmax,self.ymax*0.6250), lines )    # 2nd W Forecast
        pygame.draw.line( self.screen, line_color, (self.xmax*xmin,self.ymax*0.8125),
                            (self.xmax,self.ymax*0.8125), lines )    # 3rd W Forecast

    ####################################################################
    def sPrint(self, text, font, x, line_number, text_color):
        rendered_font = font.render(text, True, text_color)
        self.screen.blit(rendered_font, (x, self.ymax * 0.075 * line_number))

    ####################################################################
    def disp_info(self, in_daylight, day_hrs, day_mins, seconds_til_daylight,
                  delta_seconds_til_dark):
        # Fill the screen with black
        self.screen.fill((0, 0, 0))
        xmin = 10
        lines = 2
        line_color = (0, 0, 0)      #black lines to hide them
        text_color = (255, 255, 255)
        font_name = "freesans"

        # Draw Screen Border
        pygame.draw.line(self.screen, line_color,
                         (xmin, 0), (self.xmax, 0), lines)
        pygame.draw.line(self.screen, line_color,
                         (xmin, 0), (xmin, self.ymax), lines)
        pygame.draw.line(self.screen, line_color,
                         (xmin, self.ymax), (self.xmax, self.ymax), lines)
        pygame.draw.line(self.screen, line_color,
                         (self.xmax, 0), (self.xmax, self.ymax), lines)
        pygame.draw.line(self.screen, line_color,
                         (xmin, self.ymax * 0.15),
                         (self.xmax, self.ymax * 0.15), lines)

        time_height = self.time_text_height
        time_secs_height = self.time_seconds_text_height
        date_height = self.date_text_height

        # Time & Date
        time_font = pygame.font.SysFont(
            font_name, int(self.ymax * time_height), bold=0)
        time_seconds_font = pygame.font.SysFont(
            font_name, int(self.ymax * time_secs_height), bold=0)
        date_font = pygame.font.SysFont(
            font_name, int(self.ymax * date_height), bold=0)

        time_string = time.strftime("%H:%M", time.localtime())
        secs_string = time.strftime("%S", time.localtime())
        date_string = time.strftime("%A, %d %B", time.localtime()).title()

        rendered_time_string = time_font.render(time_string, True,
                                                     text_color)
        (rendered_time_x, rendered_time_y) = rendered_time_string.get_size()
        rendered_secs_string = time_seconds_font.render(secs_string, True,
                                                  text_color)
        (rendered_secs_x, rendered_secs_y) = rendered_secs_string.get_size()
        rendered_date_string = date_font.render(date_string, True,
                                                   text_color)
        (rendered_date_x, rendered_date_y) = rendered_date_string.get_size()

        full_time_string_x_position = ( self.xmax * self.window_division_x ) / 2 - (rendered_time_x+ 2*rendered_secs_y/1.4) / 2
        self.screen.blit(rendered_time_string, (full_time_string_x_position,
                                                self.time_y_position))
        self.screen.blit(rendered_secs_string,
                         (full_time_string_x_position + rendered_time_x + 3,
                          self.time_seconds_y_position))

        full_date_string_x_position = self.xmax * self.window_division_x / 2 - rendered_date_x / 2
        self.screen.blit(rendered_date_string,
                         (full_date_string_x_position, rendered_time_y -15) )
        # Date located to the time right
        #full_date_string_x_position = self.xmax / 2 + full_time_string_x_position / 2 + (rendered_time_x+ 2*rendered_secs_y/1.4) / 2 - rendered_date_x / 2  
        #self.screen.blit(rendered_date_string,
        #                 (full_date_string_x_position, self.time_y_position + 0.84 * (rendered_time_y - rendered_date_y) ) )
       
        # Info
        self.sPrint("A weather rock powered by Dark Sky", date_font,
                    self.xmax * 0.05, 5, text_color)

        self.sPrint("Sunrise: %s" % self.sunrise_string,
                    date_font, self.xmax * 0.05, 6, text_color)

        self.sPrint("Sunset:  %s" % self.sunset_string,
                    date_font, self.xmax * 0.05, 7, text_color)

        text = "Daylight: %d hrs %02d min" % (day_hrs, day_mins)
        self.sPrint(text, date_font, self.xmax * 0.05, 8, text_color)

        # leaving row 7 blank

        if in_daylight:
            text = "Sunset in %d hrs %02d min" % stot(delta_seconds_til_dark)
        else:
            text = "Sunrise in %d hrs %02d min" % stot(seconds_til_daylight)
        self.sPrint(text, date_font, self.xmax * 0.05, 9, text_color)

        # leaving row 9 blank

        text = "Weather checked at"
        self.sPrint(text, date_font, self.xmax * 0.05, 10, text_color)

        text = "    %s" % time.strftime(
            "%H:%M:%S %Z on %a. %d %b %Y ",
            time.localtime(self.last_update_check))
        self.sPrint(text, date_font, self.xmax * 0.05, 11, text_color)

        # Update the display
        pygame.display.update()

    # Save a jpg image of the screen.
    ####################################################################
    def screen_cap(self):
        pygame.image.save(self.screen, "screenshot.jpeg")
        print("Screen capture complete.")


# Given a sunrise and sunset unix timestamp,
# return true if current local time is between sunrise and sunset. In other
# words, return true if it's daytime and the sun is up. Also, return the
# number of hours:minutes of daylight in this day. Lastly, return the number
# of seconds until daybreak and sunset. If it's dark, daybreak is set to the
# number of seconds until sunrise. If it daytime, sunset is set to the number
# of seconds until the sun sets.
#
# So, five things are returned as:
#  (InDaylight, Hours, Minutes, secToSun, secToDark).
############################################################################
def daylight(weather):
    inDaylight = False    # Default return code.

    # Get current datetime with tz's local day and time.
    tNow = datetime.datetime.now()

    # Build a datetime variable from a unix timestamp for today's sunrise.
    tSunrise = datetime.datetime.fromtimestamp(weather.daily[0].sunriseTime)
    tSunset = datetime.datetime.fromtimestamp(weather.daily[0].sunsetTime)

    # Test if current time is between sunrise and sunset.
    if (tNow > tSunrise) and (tNow < tSunset):
        inDaylight = True        # We're in Daytime
        delta_seconds_til_dark = tSunset - tNow
        seconds_til_daylight = 0
    else:
        inDaylight = False        # We're in Nighttime
        delta_seconds_til_dark = 0            # Seconds until dark.
        # Delta seconds until daybreak.
        if tNow > tSunset:
            # Must be evening - compute sunrise as time left today
            # plus time from midnight tomorrow.
            sunrise_tomorrow = datetime.datetime.fromtimestamp(
                weather.daily[1].sunriseTime)
            seconds_til_daylight = sunrise_tomorrow - tNow
        else:
            # Else, must be early morning hours. Time to sunrise is
            # just the delta between sunrise and now.
            seconds_til_daylight = tSunrise - tNow

    # Compute the delta time (in seconds) between sunrise and set.
    dDaySec = tSunset - tSunrise        # timedelta in seconds
    (dayHrs, dayMin) = stot(dDaySec)    # split into hours and minutes.

    return (inDaylight, dayHrs, dayMin, seconds_til_daylight,
            delta_seconds_til_dark)


# Create an instance of the lcd display class.
MY_DISP = MyDisplay()

RUNNING = True             # Stay running while True
SECONDS = 0                # Seconds Placeholder to pace display.
# Display timeout to automatically switch back to weather dispaly.
NON_WEATHER_TIMEOUT = 0
# Switch to info periodically to prevent screen burn
PERIODIC_INFO_ACTIVATION = 0

# Loads data from darksky.net into class variables.
if MY_DISP.get_forecast() is False:
    print('Error: no data from darksky.net.')
    RUNNING = False


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
while RUNNING:
    # Look for and process keyboard events to change modes.
    for event in pygame.event.get():
        if event.type == pygame.KEYDOWN:
            # On 'q' or keypad enter key, quit the program.
            if ((event.key == pygame.K_KP_ENTER) or (event.key == pygame.K_q)):
                RUNNING = False

            # On 'd' key, set mode to 'weather'.
            elif event.key == pygame.K_d:
                MODE = 'd'
                NON_WEATHER_TIMEOUT = 0
                PERIODIC_INFO_ACTIVATION = 0

            # On 's' key, save a screen shot.
            elif event.key == pygame.K_s:
                MY_DISP.screen_cap()

            # On 'i' key, set mode to 'info'.
            elif event.key == pygame.K_i:
                MODE = 'i'
                NON_WEATHER_TIMEOUT = 0
                PERIODIC_INFO_ACTIVATION = 0

            # on 'h' key, set mode to 'hourly'
            elif event.key == pygame.K_h:
                MODE = 'h'
                NON_WEATHER_TIMEOUT = 0
                PERIODIC_INFO_ACTIVATION = 0

    # Automatically switch back to weather display after a couple minutes.
    if MODE not in ('d', 'h'):
        PERIODIC_INFO_ACTIVATION = 0
        NON_WEATHER_TIMEOUT += 1
        # Five minute timeout at 100ms loop rate.
        if NON_WEATHER_TIMEOUT > 3000:
            MODE = 'd'
            syslog.syslog("Switched to weather mode")
    else:
        NON_WEATHER_TIMEOUT = 0
        PERIODIC_INFO_ACTIVATION += 1
        CURR_MIN_INT = int(datetime.datetime.now().strftime("%M"))
        # 15 minute timeout at 100ms loop rate
        if PERIODIC_INFO_ACTIVATION > 9000:
            MODE = 'i'
            syslog.syslog("Switched to info mode")
        elif PERIODIC_INFO_ACTIVATION > 600 and CURR_MIN_INT % 2 == 0:
            MODE = 'h'
        elif PERIODIC_INFO_ACTIVATION > 600:
            MODE = 'd'

    # Daily Weather Display Mode
    if MODE == 'd':
        # Update / Refresh the display after each second.
        if SECONDS != time.localtime().tm_sec:
            SECONDS = time.localtime().tm_sec
            MY_DISP.disp_weather()
            # ser.write("Weather\r\n")
        # Once the screen is updated, we have a full second to get the weather.
        # Once per minute, update the weather from the net.
        if SECONDS == 0:
            try:
                MY_DISP.get_forecast()
            except ValueError:  # includes simplejson.decoder.JSONDecodeError
                print("Decoding JSON has failed", sys.exc_info()[0])
            except BaseException:
                print("Unexpected error:", sys.exc_info()[0])
    # Hourly Weather Display Mode
    elif MODE == 'h':
        # Update / Refresh the display after each second.
        if SECONDS != time.localtime().tm_sec:
            SECONDS = time.localtime().tm_sec
            MY_DISP.disp_hourly()
        # Once the screen is updated, we have a full second to get the weather.
        # Once per minute, update the weather from the net.
        if SECONDS == 0:
            try:
                MY_DISP.get_forecast()
            except ValueError:  # includes simplejson.decoder.JSONDecodeError
                print("Decoding JSON has failed", sys.exc_info()[0])
            except BaseException:
                print("Unexpected error:", sys.exc_info()[0])
    # Info Screen Display Mode
    elif MODE == 'i':
        # Pace the screen updates to once per second.
        if SECONDS != time.localtime().tm_sec:
            SECONDS = time.localtime().tm_sec

            (inDaylight, dayHrs, dayMins, seconds_til_daylight,
             delta_seconds_til_dark) = daylight(MY_DISP.weather)

            # Extra info display.
            MY_DISP.disp_info(inDaylight, dayHrs, dayMins,
                              seconds_til_daylight,
                              delta_seconds_til_dark)
        # Refresh the weather data once per minute.
        if int(SECONDS) == 0:
            try:
                MY_DISP.get_forecast()
            except ValueError:  # includes simplejson.decoder.JSONDecodeError
                print("Decoding JSON has failed", sys.exc_info()[0])
            except BaseException:
                print("Unexpected error:", sys.exc_info()[0])

    (inDaylight, dayHrs, dayMins, seconds_til_daylight,
     delta_seconds_til_dark) = daylight(MY_DISP.weather)

    # Loop timer.
    pygame.time.wait(100)


pygame.quit()

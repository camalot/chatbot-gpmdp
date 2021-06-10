# -*- coding: utf-8 -*-
#---------------------------------------
#   Import Libraries
#---------------------------------------
import sys
import clr
import json
import codecs
import os
import re
import random
import datetime
import glob
import time
import threading
import shutil
import tempfile
import urllib
from HTMLParser import HTMLParser
import argparse
import logging
from logging.handlers import TimedRotatingFileHandler

clr.AddReference("IronPython.SQLite.dll")
clr.AddReference("IronPython.Modules.dll")

#---------------------------------------
#   [Required] Script Information
#---------------------------------------
ScriptName = "LastFM Track Info"
Website = "http://darthminos.tv"
Description = "Retrieve Information for the current playing track from LastFM"
Creator = "DarthMinos"
Version = "1.0.0-snapshot"
Repo = "camalot/chatbot-gpmdp"
ReadMeFile = "https://github.com/" + Repo + "/blob/develop/README.md"

UIConfigFile = os.path.join(os.path.dirname(__file__), "UI_Config.json")
SettingsFile = os.path.join(os.path.dirname(os.path.realpath(__file__)), "settings.json")

GPMDPPlaybackFile = os.path.join(os.getenv('APPDATA'), "Google Play Music Desktop Player/json_store/playback.json")
LastFMDataUrl = "http://obs-lastfm.herokuapp.com/api/user/tracks/"

ScriptSettings = None
Initialized = False
Logger = None

class Settings(object):
    """ Class to hold the script settings, matching UI_Config.json. """

    def __init__(self, settingsfile=None):
        """ Load in saved settings file if available else set default values. """
        defaults = self.DefaultSettings(UIConfigFile)
        try:
            with codecs.open(settingsfile, encoding="utf-8-sig", mode="r") as f:
                settings = json.load(f, encoding="utf-8")
            self.__dict__ = Merge(defaults, settings)
        except Exception as ex:
            if Logger:
                Logger.error(str(ex))
            else:
                Parent.Log(ScriptName, str(ex))
            self.__dict__ = defaults
        # try:
        #     self.Command = "!track"
        #     self.Cooldown = 30
        #     self.PlayingMessage = "🎶🎵🎵🎶 Now playing: $GPMARTIST - $GPMTITLE 🎶🎵🎵🎶"
        #     self.NotPlayingMessage = "Nothing is currently playing. Last Played was: $GPMARTIST - $GPMTITLE 🎶🎵🎵🎶"
        #     with codecs.open(settingsfile, encoding="utf-8-sig", mode="r") as f:
        #         fileSettings = json.load(f, encoding="utf-8")
        #         self.__dict__.update(fileSettings)

        # except Exception as e:
        #     Parent.Log(ScriptName, str(e))
    
    def DefaultSettings(self, settingsfile=None):
        defaults = dict()
        with codecs.open(settingsfile, encoding="utf-8-sig", mode="r") as f:
            ui = json.load(f, encoding="utf-8")
        for key in ui:
            if 'value' in ui[key]:
                try:
                    defaults[key] = ui[key]['value']
                except:
                    if key != "output_file":
                        if Logger:
                            Logger.warn("DefaultSettings(): Could not find key {0} in settings".format(key))
                        else:
                            Parent.Log(ScriptName, "DefaultSettings(): Could not find key {0} in settings".format(key))
        return defaults

    def Reload(self, jsonData):
        """ Reload settings from the user interface by given json data. """
        # Parent.Log(ScriptName, "Reload Settings")
        # fileLoadedSettings = json.loads(jsonData, encoding="utf-8")
        # self.__dict__.update(fileLoadedSettings)
        if Logger:
            Logger.debug("Reload Settings")
        else:
            Parent.Log(ScriptName, "Reload Settings")
        self.__dict__ = Merge(self.DefaultSettings(UIConfigFile), json.loads(jsonData, encoding="utf-8"))

class StreamlabsLogHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            message = self.format(record)
            Parent.Log(ScriptName, message)
            self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)

def GetLogger():
    log = logging.getLogger(ScriptName)
    log.setLevel(logging.DEBUG)

    sl = StreamlabsLogHandler()
    sl.setFormatter(logging.Formatter("%(funcName)s(): %(message)s"))
    sl.setLevel(logging.INFO)
    log.addHandler(sl)

    fl = TimedRotatingFileHandler(filename=os.path.join(os.path.dirname(
        __file__), "info"), when="w0", backupCount=8, encoding="utf-8")
    fl.suffix = "%Y%m%d"
    fl.setFormatter(logging.Formatter(
        "%(asctime)s  %(funcName)s(): %(levelname)s: %(message)s"))
    fl.setLevel(logging.INFO)
    log.addHandler(fl)

    if ScriptSettings.DebugMode:
        dfl = TimedRotatingFileHandler(filename=os.path.join(os.path.dirname(
            __file__), "debug"), when="h", backupCount=24, encoding="utf-8")
        dfl.suffix = "%Y%m%d%H%M%S"
        dfl.setFormatter(logging.Formatter(
            "%(asctime)s  %(funcName)s(): %(levelname)s: %(message)s"))
        dfl.setLevel(logging.DEBUG)
        log.addHandler(dfl)

    log.debug("Logger initialized")
    return log
def Init():
    global ScriptSettings
    global Initialized
    global Logger
    if Initialized:
        Logger.debug("Skip Initialization. Already Initialized.")
        return
    ScriptSettings = Settings(SettingsFile)
    Logger = GetLogger()
    Logger.debug("Initialize GPMDP")
    # Load saved settings and validate values
    Initialized = True
    return

def Unload():
    global Initialized
    Initialized = False
    return


def Execute(data):

    if data.IsChatMessage():
        commandTrigger = data.GetParam(0).lower()
        if commandTrigger == ScriptSettings.Command:
            Logger.debug("Got command: {0}".format(commandTrigger))
            if not Parent.IsOnCooldown(ScriptName, commandTrigger):
                if Parent.HasPermission(data.User, ScriptSettings.Permission, ""):
                    Logger.debug("Add cooldown to command: {0} / {1}".format(commandTrigger, ScriptSettings.Cooldown))
                    Parent.AddCooldown(ScriptName, commandTrigger, ScriptSettings.Cooldown)
                    # if ScriptSettings.UseLastFM:
                    Logger.debug("Processing lastfm url")
                    ProcessLastFM()
                    # else:
                    #     if os.path.exists(GPMDPPlaybackFile):
                    #         Logger.debug("Processing GPMDP file")
                    #         ProcessGPMDPFile()

    return

def ProcessLastFM():
    try:
        Logger.debug("Get data for lastfm user: {0}".format(ScriptSettings.LastFMUser))
        url = "{0}{1}?token={2}".format(LastFMDataUrl, ScriptSettings.LastFMUser, Parent.GetChannelName())
        Logger.debug("Get url: {0}".format(url))
        response = json.loads(Parent.GetRequest(url, headers={}))['response']
        Logger.debug(response)
        data = json.loads(response)
        Logger.debug(json.dumps(data))
        message = None
        if data:
            artist = None
            album = None
            track = None

            if 'artist' in data:
                artist = data['artist']
            if 'album' in data:
                album = data['album']
            if 'title' in data:
                track = data['title']

            message = ParsePlayback(ScriptSettings.PlayingMessage, {
                "song": {
                    "artist": artist,
                    "title": track,
                    "album": album
                }
            })
        else:
            if ScriptSettings.NotPlayingMessage:
                message = ParsePlayback(ScriptSettings.NotPlayingMessage, None)


        if message:
            Parent.SendTwitchMessage(message)
    except Exception as ex:
        Logger.error(ex)


def ProcessGPMDPFile():
    filePath = GPMDPPlaybackFile
    playback = None
    with open(filePath) as f:
        playback = json.load(f)
        if playback and 'playing' in playback:
            # Format the now playing message
            message = ParsePlayback(ScriptSettings.PlayingMessage, playback)
        else:
            if ScriptSettings.NotPlayingMessage:
                message = ParsePlayback(ScriptSettings.NotPlayingMessage, playback)
        if message:
            Parent.SendTwitchMessage(message)
def Tick():
    return


def ScriptToggled(state):
    Parent.Log(ScriptName, "State Changed: " + str(state))
    if state:
        Init()
    else:
        Unload()
    return

# ---------------------------------------
# [Optional] Reload Settings (Called when a user clicks the Save Settings button in the Chatbot UI)
# ---------------------------------------
def ReloadSettings(jsondata):
    Parent.Log(ScriptName, "Reload Settings")
    # Reload saved settings and validate values
    Unload()
    Init()
    return

def Parse(parseString, user, target, message):
    resultString = parseString or ""
    return resultString


def Merge(source, destination):
    """
    >>> a = { 'first' : { 'all_rows' : { 'pass' : 'dog', 'number' : '1' } } }
    >>> b = { 'first' : { 'all_rows' : { 'fail' : 'cat', 'number' : '5' } } }
    >>> merge(b, a) == { 'first' : { 'all_rows' : { 'pass' : 'dog', 'fail' : 'cat', 'number' : '5' } } }
    True
    """
    for key, value in source.items():
        if isinstance(value, dict):
            # get node or create one
            node = destination.setdefault(key, {})
            Merge(value, node)
        elif isinstance(value, list):
            destination.setdefault(key, value)
        else:
            if key in destination:
                pass
            else:
                destination.setdefault(key, value)

    return destination

def str2bool(v):
    if not v:
        return False
    return stripQuotes(v).strip().lower() in ("yes", "true", "1", "t", "y")

def ParsePlayback(message, data):
    result = message or ""
    Logger.debug(json.dumps(data))
    if data and 'song' in data:
        if "$GPMARTIST" in result:
            if 'artist' in data['song']:
                result = result.replace("$GPMARTIST", data['song']['artist'] or "UNKNOWN")
            else:
                result = result.replace("$GPMARTIST", "UNKNOWN")
        if "$GPMTITLE" in result:
            if 'title' in data['song']:
                result = result.replace("$GPMTITLE", data['song']['title'] or "UNKNOWN")
            else:
                result = result.replace("$GPMTITLE", "UNKNOWN")
        if "$GPMALBUM" in result:
            if 'album' in data['song']:
                result = result.replace("$GPMALBUM", data['song']['album'] or "UNKNOWN")
            else:
                result = result.replace("$GPMALBUM", "UNKNOWN")
    else:
        result = result.replace("$GPMARTIST", "").replace("$GPMTITLE", "").replace("$GPMALBUM", "UNKNOWN")
    return result

def urlEncode(v):
    return urllib.quote(v)

def stripQuotes(v):
    r = re.compile(r"^[\"\'](.*)[\"\']$", re.U)
    m = r.search(v)
    if m:
        return m.group(1)
    return v

def random_line(filename):
    with open(filename) as f:
        lines = f.readlines()
        return random.choice(lines).strip()

def OpenScriptUpdater():
    currentDir = os.path.realpath(os.path.dirname(__file__))
    chatbotRoot = os.path.realpath(os.path.join(currentDir, "../../../"))
    libsDir = os.path.join(currentDir, "libs/updater")
    Parent.Log(ScriptName, libsDir)
    try:
        src_files = os.listdir(libsDir)
        tempdir = tempfile.mkdtemp()
        Parent.Log(ScriptName, tempdir)
        for file_name in src_files:
            full_file_name = os.path.join(libsDir, file_name)
            if os.path.isfile(full_file_name):
                Parent.Log(ScriptName, "Copy: " + full_file_name)
                shutil.copy(full_file_name, tempdir)
        updater = os.path.join(tempdir, "ApplicationUpdater.exe")
        updaterConfigFile = os.path.join(tempdir, "update.manifest")
        repoVals = Repo.split('/')
        updaterConfig = {
            "path": os.path.realpath(os.path.join(currentDir, "../")),
            "version": Version,
            "name": ScriptName,
            "requiresRestart": True,
            "kill": [],
            "execute": {
                "before": [{
                    "command": "cmd",
                    "arguments": [ "/c", "del /q /f /s *" ],
                    "workingDirectory": "${PATH}\\${FOLDERNAME}\\Libs\\updater\\",
                    "ignoreExitCode": True,
                    "validExitCodes": [ 0 ]
                }],
                "after": []
            },
            "application": os.path.join(chatbotRoot, "Streamlabs Chatbot.exe"),
            "folderName": os.path.basename(os.path.dirname(os.path.realpath(__file__))),
            "processName": "Streamlabs Chatbot",
            "website": Website,
            "repository": {
                "owner": repoVals[0],
                "name": repoVals[1]
            }
        }
        Parent.Log(ScriptName, updater)
        configJson = json.dumps(updaterConfig)
        Parent.Log(ScriptName, configJson)
        with open(updaterConfigFile, "w+") as f:
            f.write(configJson)
        os.startfile(updater)
        return
    except OSError as exc:  # python >2.5
        raise
    return


def OpenFollowOnTwitchLink():
    os.startfile("https://twitch.tv/DarthMinos")
    return

def OpenReadMeLink():
    os.startfile(ReadMeFile)
    return

def OpenPaypalDonateLink():
    os.startfile("https://paypal.me/camalotdesigns/10")
    return
def OpenGithubDonateLink():
    os.startfile("https://github.com/sponsors/camalot")
    return
def OpenTwitchDonateLink():
    os.startfile("http://twitch.tv/darthminos/subscribe")
    return

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

clr.AddReference("IronPython.SQLite.dll")
clr.AddReference("IronPython.Modules.dll")

#---------------------------------------
#   [Required] Script Information
#---------------------------------------
ScriptName = "Google Play Music Desktop Player Track Info"
Website = "http://darthminos.tv"
Description = "Retrieve Information for the current playing track from GPMDP"
Creator = "DarthMinos"
Version = "1.0.0-snapshot"
Repo = "camalot/chatbot-gpmdp"
ReadMeFile = "https://github.com/" + Repo + "/blob/develop/README.md"

SettingsFile = os.path.join(os.path.dirname(
    os.path.realpath(__file__)), "settings.json")

ScriptSettings = None
Initialized = False

class Settings(object):
    """ Class to hold the script settings, matching UI_Config.json. """

    def __init__(self, settingsfile=None):
        """ Load in saved settings file if available else set default values. """
        try:
            self.Command = "!track"
            self.Cooldown = 30
            self.PlayingMessage = "🎶🎵🎵🎶 Now playing: $GPMARTIST - $GPMTITLE 🎶🎵🎵🎶"
            self.NotPlayingMessage = "Nothing is currently playing. Last Played was: $GPMARTIST - $GPMTITLE 🎶🎵🎵🎶"
            with codecs.open(settingsfile, encoding="utf-8-sig", mode="r") as f:
                fileSettings = json.load(f, encoding="utf-8")
                self.__dict__.update(fileSettings)

        except Exception as e:
            Parent.Log(ScriptName, str(e))

    def Reload(self, jsonData):
        """ Reload settings from the user interface by given json data. """
        Parent.Log(ScriptName, "Reload Settings")
        fileLoadedSettings = json.loads(jsonData, encoding="utf-8")
        self.__dict__.update(fileLoadedSettings)


def Init():
    global ScriptSettings
    global Initialized
    if Initialized:
        Parent.Log(ScriptName, "Skip Initialization. Already Initialized.")
        return
    Parent.Log(ScriptName, "Initialize")
    # Load saved settings and validate values
    ScriptSettings = Settings(SettingsFile)
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
            filePath = os.path.join(os.getenv('APPDATA'), "Google Play Music Desktop Player/json_store/playback.json")
            Parent.Log(ScriptName, filePath)
            playback = None
            with open(filePath) as f:
                playback = json.load(f)

                if not Parent.IsOnCooldown(ScriptName, commandTrigger):
                    if Parent.HasPermission(data.User, ScriptSettings.Permission, ""):
                        Parent.AddCooldown(ScriptName, commandTrigger, ScriptSettings.Cooldown)
                        if playback and playback['playing']:
                            # Format the now playing message
                            message = ParsePlayback(ScriptSettings.PlayingMessage, playback)
                        else:
                            if ScriptSettings.NotPlayingMessage:
                                message = ParsePlayback(ScriptSettings.NotPlayingMessage, playback)
                        if message:
                            Parent.SendTwitchMessage(message)

    return


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

def str2bool(v):
    if not v:
        return False
    return stripQuotes(v).strip().lower() in ("yes", "true", "1", "t", "y")

def ParsePlayback(message, data):
    result = message or ""
    Parent.Log(ScriptName, json.dumps(data))
    if data and 'song' in data:
        if "$GPMARTIST" in result:
            result = result.replace("$GPMARTIST", data['song']['artist'] or "UNKNOWN")
        if "$GPMTITLE" in result:
            result = result.replace("$GPMTITLE", data['song']['title'] or "UNKNOWN")
        if "$GPMALBUM" in result:
            result = result.replace("$GPMALBUM", data['song']['album'] or "UNKNOWN")
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

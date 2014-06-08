# -*- coding: utf-8 -*-

from collections import OrderedDict
import os
import uuid

import constants
from misc import trySymlink, tryMkdir


class MountsFaker(object):
    # Terminlogies:
    # local path: a path that the user sets
    # mnt path: the path which is mapped from a local path
    #           for example, PROFILE/mnt/mnt\unix

    _mounts = None

    def __init__(self):
        self._mounts = OrderedDict()

        with open(constants.MOUNTS_FILE, "r", encoding = "UTF-8") as mountsFile:
            lines = mountsFile.readlines()
            for line in lines:
                if line.replace("\t", "").replace(" ", "").replace("\n", "") == "":
                    continue  # empty line

                lstripped = line.lstrip()
                if len(lstripped) > 0 and lstripped[0] == "#":
                    continue  # comment

                parts = line.split()
                path, uuid_ = parts[1], parts[0][len("UUID="):]

                self._mounts[path] = uuid_

    @property
    def mounts(self):
        # encapsulate self._mounts, which is an ordereddict of <path:uuid>
        # only expose a list of <path>
        return list(map(self._getLocalPath, self._mounts.keys()))

    @mounts.setter
    def mounts(self, paths):
        newMounts = OrderedDict()
        for unixPath in paths:
            mntPath = self._mountBootstrap(unixPath)
            newMounts[mntPath] = self._mounts.get(mntPath, str(uuid.uuid1()))

        # write mount file
        buffer = list()
        buffer.append(constants.MOUNTS_FILE_HEADER)

        for path, uuid_ in newMounts.items():
            # we only care about the first two columns
            buffer.append("UUID={uuid} {path} auto defaults,rw 0 0".format(uuid = uuid_,
                                                                           path = path))

        buffer.append("")

        with open(constants.MOUNTS_FILE, "w", encoding = "UTF-8") as mountFile:
            mountFile.writelines("\n".join(buffer))

        self._mounts = newMounts

    def convertToLocalPath(self, path):
        # takes a path like "/tmp/thunder/volumes/C:/TDDOWNLOAD/1.zip"
        # returns a local path "/home/user/Download/1.zip"

        assert path[:len(constants.ETM_MOUNTS_DIR)] == constants.ETM_MOUNTS_DIR

        path = path[len(constants.ETM_MOUNTS_DIR):]  # remove "/tmp/thunder/volumes/" prefix
        parts = path.split("/")  # ["C:", "TDDOWNLOAD", "1.zip"]
        drive = parts[0][:-1]  # "C:" -> "C"

        localPath = os.path.join(
            self.mounts[ord(drive) - ord("C")],
            *parts[2:]  # discard "C:" and "TDDOWNLOAD"
        )
        resolvedLocalPath = os.path.realpath(localPath)

        return resolvedLocalPath

    @staticmethod
    def getMountsMapping():
        # checks when ETM really uses
        mapping = {}
        try:
            for drive in os.listdir(constants.ETM_MOUNTS_DIR_WITHOUT_CHMNS):
                # drive is like "C:", "D:"
                realpath = os.path.realpath(constants.ETM_MOUNTS_DIR_WITHOUT_CHMNS + drive)
                mapping[realpath] = drive
        except FileNotFoundError:
            pass
        return mapping

    @staticmethod
    def driveIndexToLetter(index):
        # 0 -> "C:", 1 -> "D:", ...
        return chr(ord('C') + index) + ":"

    @staticmethod
    def _mountBootstrap(localPath):
        # local/path is the path that user sets
        # after bootstraping, return the path to PROFILE/mnt/local\path

        # the filter(bool) part is to remove the "/" at the beginning
        backslashed = "\\".join(filter(bool, localPath.split("/")))

        mntDir = os.path.join(constants.PROFILE_DIR, "mnt", backslashed)

        tddownloadDir = os.path.join(mntDir, "TDDOWNLOAD")
        thunderdbDir = os.path.join(mntDir, "ThunderDB")

        tryMkdir(thunderdbDir)
        trySymlink(localPath, tddownloadDir)

        return mntDir

    @staticmethod
    def _getLocalPath(mntPath):
        # takes an mnt path, and returns a local path
        mntPath = os.path.normpath(mntPath)
        part = mntPath[mntPath.rindex("/"):]
        return part.replace("\\", "/")

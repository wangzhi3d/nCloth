#!/usr/bin/env python
# coding=cp936
# coding=utf-8

import maya.cmds as cmds
import pymel.core as pm
import maya.mel as mel
import maya.OpenMaya as OpenMaya
import threading
import os
import shutil
import toolbox_library.system.__displayViewPrint as display
from xml.etree import ElementTree as ET
import functools

try:
    from maya.utils import executeInMainThreadWithResult
except:
    executeInMainThreadWithResult = None


class Timer(threading.Thread):
    def __init__(self, interval, function, repeat=True, *args, **kwargs):
        self.interval = interval
        self.function = function
        self.repeat = repeat
        self.args = args
        self.kwargs = kwargs
        self.event = threading.Event()
        threading.Thread.__init__(self)

    def run(self):
        def _mainLoop():
            if not self.interval is None:
                self.event.wait(self.interval)
            if not self.event.isSet():
                if executeInMainThreadWithResult:
                    executeInMainThreadWithResult(self.function, self.stop, self.args, **self.kwargs)
                else:
                    self.function(self.stop, *self.args, **self.kwargs)

        if self.repeat:
            while not self.event.isSet():
                _mainLoop()
        else:
            _mainLoop()
            self.stop()

    def start(self):
        self.event.clear()
        threading.Thread.start(self)

    def stop(self):
        self.event.set()
        threading.Thread.__init__(self)



class CacheNucleus(object):

    TYPE = ['nCloth', 'hairSystem']

    def __init__(self, Data=list()):

        self.addShowDisplay = "showDisplay_nucleus"

        self.StartTime = None
        self.EndTime =None

        self.CalculationList = list()
        self.SaveCacheDir = None

        self.SaveCacheStatus = False
        self.UpTimeStatus = False

        self.ActiveCacheNodeDict = dict()
        self.cacheData = Data

        self.SelctShapeList = self.getSelectCacheShapeNode()

        self.getUersTimer()
        self.__getNucleusConnectType__()


    def __getNucleusConnectType__(self):

        self.CalculationList = cmds.ls(type=self.TYPE)
        if self.CalculationList:
            self.getActiveCacheNode()

        if not self.ActiveCacheNodeDict:
            self.__getUersProjectDir()
            self.newCreateCache()
        else:
            self.getActiveCacheFileNode()

    def getActiveCacheNode(self):
        for node in self.CalculationList:
            cacheList = mel.eval("""findExistingCaches("%s")""" % node)
            if not cacheList:
                self.__CreateCache__(node)
                cacheList = mel.eval("""findExistingCaches("%s")""" % node)
            for i in cacheList:
                if cmds.getAttr(i+".enable"):
                    self.ActiveCacheNodeDict[node] = i
                    if not self.SaveCacheStatus:
                        self.SaveCacheStatus = True

                    info = mel.eval("""getNClothDescriptionInfo("%s")""" % node)

    def getActiveCacheFileNode(self):

        for key, value in self.ActiveCacheNodeDict.items():
            listFile = cmds.cacheFile(value, query=True, f=True)

            filePath = None
            if listFile:
                filePath = os.path.dirname(listFile[0])

            self.ActiveCacheNodeDict[key] = [value, filePath]


    def __getUersProjectDir(self):

        projectPath = os.path.dirname(cmds.workspace(query=True, rootDirectory=True))
        sceneName = cmds.file(query=True, sceneName=True)

        if sceneName:
            fileName = os.path.basename(sceneName)
            Name, fileType = fileName.split(".")
            untitled = Name
        else:
            untitled = "untitled"

        dirPath = os.path.join(projectPath, 'cache', 'nCache', untitled)

        edition = 0
        while True:
            if edition == 0:
                newDirPath = dirPath
            else:
                newDirPath = dirPath + str(edition)

            if os.path.isdir(newDirPath):
                if not os.listdir(newDirPath):
                    break
                else:
                    edition += 1
            else:
                break

        self.SaveCacheDir = newDirPath.replace('\\','/')

        if not os.path.isdir(self.SaveCacheDir):
            os.makedirs(self.SaveCacheDir)

    def getUersTimer(self):

        self.StartTime = cmds.playbackOptions(query=True, minTime=True)
        self.EndTime = cmds.playbackOptions(query=True, maxTime=True)


    def delectCache(self, endValue=None, startValue=None):

        if not self.SaveCacheStatus:
            return display.displayViewPrint(u'<hl style=\"color:#FF4500\">场景没有缓存</hl>')

        if startValue is None and endValue is None:
            shapeList = self.getSelectCacheShapeNode()
            if shapeList is None:
                self.__removeCacheFile__()

            elif shapeList:
                for i in shapeList:
                    if i in self.ActiveCacheNodeDict.keys():
                        self.__removeOneCacheFile__(i)
            else:
                pass
        else:
            shapeList = self.getSelectCacheShapeNode()
            if shapeList is None:
                for index in self.ActiveCacheNodeDict.keys():
                    self.__deleteCachedFrame__(index, endValue, startValue)
            elif shapeList:
                for i in shapeList:
                    if i in self.ActiveCacheNodeDict.keys():
                        self.__deleteCachedFrame__(i, endValue, startValue)
            else:
                pass

            # status = False
            # for key, value in self.ActiveCacheNodeDict.items():
            #     if not value[1] is None:
            #         for file_index in os.listdir(value[1]):
            #             if file_index.endswith(".mcx"):
            #                 status = True
            #                 break
            #
            # if not status:
            #     self.__removeCacheFile__()

    def __deleteCachedFrame__(self, name, endValue=None, startValue=None):

        cmds.cacheFile(refresh=True, deleteCachedFrame=True, cacheableNode=name, startTime=startValue,
                       endTime=endValue)

        self.removeShowDisplay(name, False)

        filePath = self.ActiveCacheNodeDict[name][1]
        if not filePath is None:
            listFiles = filePath
            for fileName in os.listdir(listFiles):
                if fileName.startswith("backup_"):
                    try:
                        os.remove(os.path.join(filePath, fileName))
                        OpenMaya.MGlobal.displayInfo("remove files (%s)" % (os.path.join(filePath, fileName)))
                    except:
                        pass
            display.displayViewPrint(
                u'<hl style=\"color:#FF4500\"> %s (%s)至(%s)缓存已删除</hl>' % (fileName, startValue, endValue))

    def getSelectCacheShapeNode(self):
        selectNode = cmds.ls(sl=True)
        if not selectNode:
            return None
        else:
            selectShapeNode = [pm.PyNode(i).getShape().name() for i in selectNode if pm.PyNode(i).getShape()]
            cacheShapeNode = [index for index in selectShapeNode if cmds.objectType(index) in self.TYPE]

            meshShapeNode = [index for index in selectShapeNode if cmds.objectType(index) == "mesh"]
            pfxHairShapeNode = [index for index in selectShapeNode if cmds.objectType(index) == "pfxHair"]
            ClothShapeNode = [mel.eval("""findTypeInHistory("%s","nCloth",3,3)""" % i) for i in meshShapeNode]
            HairShapeNode = [mel.eval("""findTypeInHistory("%s","hairSystem",2,2)""" % i) for i in pfxHairShapeNode]

            cacheShapeNode.extend(ClothShapeNode)
            cacheShapeNode.extend(HairShapeNode)
            cacheShapeNode = [i for i in cacheShapeNode if not i is u""]
            cacheShapeNode0ne = set(cacheShapeNode)

            if len(cacheShapeNode0ne) > 0:
                return list(cacheShapeNode0ne)
            else:
                return False

    def __removeCacheFile__(self):

        for key in self.ActiveCacheNodeDict.keys():
            self.__removeOneCacheFile__(key)

        self.SaveCacheStatus = False
        return display.displayViewPrint(u'<hl style=\"color:#FF4500\">场景nucleus解算的物体缓存已删除</hl>')

    def __removeOneCacheFile__(self, name):

        value = self.ActiveCacheNodeDict[name]

        if not value[1] is None:
            try:
                if cmds.objExists(value[0]):
                    cmds.setAttr(value[0]+".enable", 0)
                    cmds.delete(value[0])
                    self.ActiveCacheNodeDict.pop(name)

                if os.path.isdir(value[1]):
                    self.__deleteFile__(value[1], name)
                    OpenMaya.MGlobal.displayInfo("remove cacheNode (%s)" % value[0])
                    display.displayViewPrint(u'<hl style=\"color:#FF4500\"> %s 缓存已删除</hl>' % value[0])

                self.removeShowDisplay(name)
            except:
                pass

    def __deleteFile__(self, path, shapeName):
        listFile = os.listdir(path)
        for fileName in listFile:
            if fileName.startswith(shapeName):
                os.remove(os.path.join(path, fileName))
                OpenMaya.MGlobal.displayInfo("remove files (%s)" % (os.path.join(path, fileName)))


    def newCreateCache(self):

        nowStartTime = cmds.playbackOptions(query=True, minTime=True)
        EndTime = cmds.playbackOptions(query=True, maxTime=True)
        if nowStartTime != self.StartTime:
            confirm = cmds.confirmDialog(title=u'确认', message=u'是否重新生成?', button=['Yes', 'No'], defaultButton='Yes',
                               cancelButton='No', dismissString='No')
            if confirm:
                self.createCache(nowStartTime)

        else:
            self.createCache(nowStartTime)

    def createCache(self, startTime = None):
        if self.ActiveCacheNodeDict:
            self.__removeCacheFile__()

        for node in self.CalculationList:
            self.__CreateCache__(node)

    def __CreateCache__(self, node):

        if not self.SaveCacheDir:
            self.__getUersProjectDir()

        if self.__getNodeStatus__(node):
            cmds.select(node, r=True)
            xmlPath = mel.eval("""doCreateNclothCache 5 { "3", "%s", "%s", "OneFilePerFrame", "1", "%s","0","","0", "add", "0", "1", "1","0","1","mcx" };""" %(self.StartTime, self.StartTime, self.SaveCacheDir))
            cmds.select(cl=True)

            cacheNode = None

            cacheList = mel.eval("""findExistingCaches("%s")""" % node)
            for i in cacheList:
                if cmds.getAttr(i+".enable"):
                    cacheNode = i

            self.ActiveCacheNodeDict[node] = [cacheNode, self.SaveCacheDir]

            if not self.SaveCacheStatus:
                self.SaveCacheStatus = True


    def xml_appendInfo(self, xml, appendList):

        if type(appendList) != list:
            return

        root = ET.parse(xml)
        rootNode = root.getroot()

        Channel = rootNode.find('Channels')
        for index in Channel:
            index.attrib['SamplingRate'] = '250'
        rootNode.remove(Channel)

        for index in appendList:
            addText = ET.Element('extra')
            addText.text = index
            rootNode.append(addText)

        rootNode.append(Channel)

        root.write(xml, encoding='utf-8')

    def getXmlInformation(self, xml):

        root = ET.parse(xml)
        channel = root.find('Channels')

        SamplingRate = int(channel[0].attrib['SamplingRate'])
        StartTime = int(channel[0].attrib['StartTime'])
        EndTime = int(channel[0].attrib['EndTime'])

        StartFrame = StartTime/SamplingRate
        EndFrame= EndTime/SamplingRate

        return StartFrame, EndFrame

    def __getNodeStatus__(self, shape):
        if cmds.objectType(shape) == self.TYPE[0]:
            if cmds.getAttr(shape + ".isDynamic"):
                return cmds.getAttr(shape + ".isDynamic")
        elif cmds.objectType(shape) == self.TYPE[1]:
            if cmds.getAttr(shape + ".simulationMethod") == 3 or cmds.getAttr(shape + ".simulationMethod") == 2:
                return True
            else:
                return False
        else:
            return False

    def appendNclothCache(self, *args, **kwargs):

        self.getUersTimer()

        if kwargs.has_key("startTime"):
            nowTime = kwargs['startTime']
        else:
            nowTime = cmds.currentTime(query=True)

        if self.SelctShapeList:
            display.displayViewPrint(u'<hl style=\"color:#FF4500\"> 为选择的(%s)创建缓存</hl>'% self.SelctShapeList)
            for s in self.SelctShapeList:
                if self.__getNodeStatus__(s):
                    cmds.cacheFile(appendFrame=True, replaceCachedFrame=True, simulationRate=1, sampleMultiplier=1, noBackup=True, cnd=s)
                    self.showDisplay(s)
        else:
            display.displayViewPrint(u'<hl style=\"color:#FF4500\"> 为场景中所有由nucleu控制的创建缓存</hl>' )
            for key, value in self.ActiveCacheNodeDict.items():
                if self.__getNodeStatus__(key):
                    cmds.cacheFile(appendFrame=True, replaceCachedFrame=True, simulationRate=1, sampleMultiplier=1, noBackup=True, cnd=key)
                    self.showDisplay(key)

        if nowTime == self.EndTime:
            if len(args) > 0:
                fun = args[0]
                cmds.iconTextButton('threadPlay', e=True, l='播放', image1="interactivePlayback.png")
                fun()
        else:
            nowTime += 1
            cmds.currentTime(nowTime)

    def showDisplay(self, shape):
        '''
        :param shape:
        :return:
        '''
        meshList = self.getCalculationToMeshNode(shape)

        for index in meshList:
            mesh = pm.PyNode(index)
            if not mesh.hasAttr(self.addShowDisplay):
                mesh.addAttr(self.addShowDisplay, at="double", dv=0, keyable=True)
            mesh.showDisplay_nucleus.setKey()

    def removeShowDisplay(self, shape, isAll = True):

        meshList = self.getCalculationToMeshNode(shape)

        endTime = cmds.playbackOptions(query=True, maxTime=True)
        nowTime = cmds.currentTime(query=True)
        nowTime += 1

        rangeTime = (nowTime, endTime)

        for index in meshList:
            mesh = pm.PyNode(index)
            if mesh.hasAttr(self.addShowDisplay):
                animList = mesh.showDisplay_nucleus.inputs()
                if isAll:
                    pm.delete(animList)
                    mesh.deleteAttr(self.addShowDisplay)
                else:
                    for anim in animList:
                        cmds.cutKey(anim.name(), clear=True, iub=False, an="objects", t=rangeTime, o="keys")


    def getCalculationToMeshNode(self, shape):

        meshList = list()
        if cmds.objectType(shape) == self.TYPE[0]:
            meshList = cmds.listConnections(shape + ".outputMesh", d=True, s=False)
        if cmds.objectType(shape) == self.TYPE[1]:
            meshList = cmds.listConnections(shape + ".outputRenderHairs", d=True, s=False)
        return meshList


class newCache(object):

    def __init__(self):
        self.UIName = 'newCacheWin'
        self.myHudButton = "myHudButton"

        self.playBack = "threadPlay"
        self.delectAllCache = "delectAllCache"
        self.deleteFrontCache = "deleteFrontCache"
        self.deleteBehindCache = "deleteBehindCache"

        self.playIcon = "interactivePlayback.png"
        self.stopIcon = "timestop.png"


        self.timer = None
        self.cacheCmd = None

    def play(self, *args):
        # hudButtonLabel = cmds.hudButton(self.myHudButton, q=True, label=True)

        playBackIcon = cmds.iconTextButton(self.playBack, q=True, image1=True)

        # if hudButtonLabel == ">Play":
        #     cmds.hudButton(self.myHudButton, e=True, label='|Stop')
        # if hudButtonLabel == "|Stop":
        #     cmds.hudButton(self.myHudButton, e=True, label='>Play')

        if playBackIcon == self.playIcon:
            cmds.iconTextButton(self.playBack, e=True, l='暂停', image1=self.stopIcon)
        if playBackIcon == self.stopIcon:
            cmds.iconTextButton(self.playBack, e=True, l='播放', image1=self.playIcon)

        if playBackIcon == self.playIcon:
            self.cacheCmd.__init__()
            if not self.cacheCmd.CalculationList or self.cacheCmd.SelctShapeList is False:
                cmds.iconTextButton(self.playBack, e=True, l='播放', image1=playBackIcon)
                return
            self.timer.start()

        if playBackIcon == self.stopIcon:
            self.timer.stop()

    # def closeHudButton(self, *args):
    #     cmds.headsUpDisplay(self.myHudButton, rem=True)

    def create_ui(self):

        if cmds.window(self.UIName, ex=True):
            cmds.deleteUI(self.UIName)

        cmds.window(self.UIName, title=u"Cache Tool", mxb=False, mnb=False)
        #cmds.window(self.UIName, e=True, wh=[169, 44])
        cmds.rowLayout(numberOfColumns=4)
        cmds.iconTextButton(self.playBack,  w=60, l='播放', style="iconAndTextVertical", image1=self.playIcon, ann="交互播放", c=self.play)
        cmds.iconTextButton(self.deleteBehindCache,  w=60, l='当前后面', style="iconAndTextVertical", image1="deleteBehindCache.png", ann="删除当前帧后面的缓存")
        cmds.iconTextButton(self.delectAllCache,  w=60, l='删除', style="iconAndTextVertical", image1="deleteActive.png", ann="删除所有缓存")
        cmds.showWindow(self.UIName)

        # cmds.hudButton(self.myHudButton, section=2, block=0, visible=True,
        #                label='>Play', buttonWidth=60, buttonShape='roundRectangle', lfs="large",
        #                releaseCommand=self.play)

    def run(self):
        self.create_ui()
        self.regainData()

    def delectCacheFrame(self, mod, *args):

        startTime = cmds.playbackOptions(query=True, minTime=True)
        endTime = cmds.playbackOptions(query=True, maxTime=True)

        nowTime = cmds.currentTime(query=True)
        nowTime += 1

        if mod == "Front":
            self.cacheCmd.delectCache(nowTime, startTime)

        if mod == "Behind":
            self.cacheCmd.delectCache(endTime, nowTime)

    def regainData(self):

        self.cacheCmd = CacheNucleus()
        self.timer = Timer(0.5, self.cacheCmd.appendNclothCache, True)

        cmds.iconTextButton(self.delectAllCache, e=True, c=self.cacheCmd.delectCache)
        cmds.iconTextButton(self.deleteBehindCache, e=True, c=functools.partial(self.delectCacheFrame, 'Behind'))


if __name__ == "__main__":
    aaa = newCache()
    aaa.run()
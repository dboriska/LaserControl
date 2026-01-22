# -*- coding: utf-8 -*-
"""
Created on Sat Jul 20 08:13:01 2019

@author: Prash HyperLight PC
Modified: Eric Puma, Harvard University
"""
#Controlling the santec tsl 5xx laser
# Copyright (c) 2019 Prashanta Kharel, HyperLight Corporation

import visa
import time

class Santec():

    def connect(self, GPIBName, rm):
        self.santeclaser = rm.open_resource(GPIBName)
        # ask to identify
        print(self.santeclaser.query('*IDN?'))
        time.sleep(0.3)
        self.setWavelengthUnit(0) # nm:0, THz:1
        time.sleep(0.3)
        self.openShutter(0)  # shutter is closed 1: shutter is open, 0: shutter is closed

        # check to power state and turn it on if it is off already
        if (int(self.santeclaser.query(':POWer:STATe?')) == 0):
            self.turnLaserDiodeON(1)
            print("Laser diode is turning on,  please wait for 2 minutes....")
            time.sleep(60)


        self.setAttenuation(30)
        time.sleep(0.3)
        self.openShutter(1)        # open the shutter 1: shutter is on

    def turnLaserDiodeON(self, onoroff):
        # onoroff: 1 means turn on the laser diode, 0 mean turn off the laser diode
        if onoroff:
            self.santeclaser.write(':POWer:STATe 1')
        else:
            self.santeclaser.write(':POWer:STATe 0')

    def setAttenuation(self, valuedB):
        self.santeclaser.write(':POW:ATT '+str(valuedB))

    def setWavelength(self, valueWavlength):
        self.santeclaser.write(':WAVelength '+str(valueWavlength))

    def openShutter(self, onoroff):
        if (onoroff):
            self.santeclaser.write(':POW:SHUT 0')
            print("Shutter is now open!")
        else:
            self.santeclaser.write(':POW:SHUT 1')
            print("Shutter is now closed!")

    def sweepSettings(self, numOfSweeps, triggerOut = True):
        self.santeclaser.write(':WAVelength:SWEep:MODe 1') # set the sweep mode to continuous, one way
        time.sleep(0.3)
        self.santeclaser.write(':WAVelength:SWEep:CYCLes '+str(numOfSweeps)) # if Range 0~999. 0 means infinite sweep
        if numOfSweeps==0:
            self.santeclaser.write(':WAV:SWE:REP') # continuously repeat the sweeps
        time.sleep(0.3)

        if triggerOut:
            # sends a trigger out at the start of a sweep
            self.santeclaser.write(':TRIGger: OUTPut 2')

        time.sleep(0.5)

        #self.startSweep()       # start the sweep

    def setSweepCycles(self, numOfSweeps):
        self.santeclaser.write(':WAVelength:SWEep:CYCLes ' + str(numOfSweeps))  # if Range 0~999. 0 means infinite sweep
        if numOfSweeps == 0:
            self.santeclaser.write(':WAV:SWE:REP')  # continuously repeat the sweeps

    def setTriggerOut(self, triggerOut = True):
        if triggerOut:
            # sends a trigger out at the start of a sweep
            self.santeclaser.write(':TRIGger: OUTPut 2')
        else:
            self.santeclaser.write(':TRIGger: OUTPut 0')

    # start the wavelength sweep
    def startSweep(self):
        #time.sleep(0.5)
        self.santeclaser.write(':WAVelength:SWEep 1')

    def startSweepLoop(self):
        self.santeclaser.write(':WAVelength:SWEep:STATe:REPeat')

    #stop the wavelength sweep
    def stopSweep(self):
        self.santeclaser.write(':WAVelength:SWEep 0')

    def setSweepSpeed(self, sweepSpeed_nm):
        self.santeclaser.write(':WAVelength:SWEep:SPEed '+str(sweepSpeed_nm))

    def setStartWavelength(self, startWavelength_nm):
        #speed_light_vacuum = 299792458
        #startfrequency = 299792458 / startWavelength_nm * 1.0e-3  # in THz
        self.santeclaser.write(':WAVelength:SWEep:STARt %.5f' % startWavelength_nm)

    def setStopWavelength(self, stopWavelength_nm):
        #speed_light_vacuum = 299792458
        #stopfrequency = 299792458 / stopWavelength_nm * 1.0e-3  # in THz
        self.santeclaser.write(':WAVelength:SWEep:STOP %.5f' % stopWavelength_nm)
        #self.laser.write(':FREQuency:SWEep:STOP %.5f' % stopfrequency)

    def setWavelengthUnit(self, onoroff):
        if onoroff==0:
            self.santeclaser.write(':WAVelength:UNIT 0') # 0 means in nm
        else:
            self.santeclaser.write(':WAVelength:UNIT 1') # 1 mean in  THz

    def getInternalPower(self):
        return self.santeclaser.query(':POWer:ACTual?')

    def disconnect(self):
        self.stopSweep() # stop the sweep
        time.sleep(0.3)
        self.setAttenuation(30)
        time.sleep(0.3)
        self.openShutter(0)
        #self.turnLaserDiodeON(0)

    def setSweepMode(self,nmode):
        self.santeclaser.write('WAVelength:SWEep:MODe ' + str(nmode))

    def setSweepStep(self,step_nm):
        self.santeclaser.write('WAVelength:SWEep:STEp ' + str(step_nm))


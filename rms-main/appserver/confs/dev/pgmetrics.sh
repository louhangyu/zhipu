#!/bin/sh


pgmetrics -h 10.10.0.39 -p 5432 -U cacti $* <<!
Cacti_12345
!

/*
 * KISS Open License Version 1.0 (KOL-v1)
 *
 * SPDX-FileCopyrightText: 2026 I-plusplus Inc.
 * SPDX-License-Identifier: LicenseRef-KOL-v1
 *
 * Copyright remains with its respective holders; original copyright and attribution notices must be preserved.
 * Contributors may add copyright notices for their own original modifications.
 * Distributed modifications must be identified as required by Section 4(c) of KOL-v1.
 *
 * Use, modification, distribution, and incorporation into commercial or proprietary software are permitted
 * without license fees or source disclosure, subject to all terms of the complete KOL-v1 license.
 *
 * Contributors grant the patent permissions stated in KOL-v1. Outputs are not covered merely because a
 * KOL-licensed tool produced them; embedded licensed material remains subject to applicable license terms.
 *
 * THIS SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OR LIABILITY TO THE EXTENT PERMITTED BY APPLICABLE LAW.
 *
 * This header is a summary, not a separate license or an amendment to KOL-v1.
 * All terms and conditions of KOL-v1 apply. See the accompanying LICENSE file for the complete license text.
 */

#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
int write_all_nb(int,const void*,size_t,size_t*);
int real_write_all_nb(int,const void*,size_t,size_t*);
typedef struct {ssize_t result; int error;} step;
static step plan[8]; static size_t total_steps, calls, accepted;
static const char data[]="abcdefghij";
ssize_t test_write(int fd,const void *buf,size_t len) {
    assert(fd==123); assert(calls<total_steps); assert(buf==data+accepted); assert(len==10-accepted);
    step s=plan[calls++]; if(s.result<0) errno=s.error; else { assert((size_t)s.result<=len); accepted+=(size_t)s.result; }
    return s.result;
}
static void scenario(const step *steps,size_t n,int result,size_t bytes,int error) {
    memcpy(plan,steps,n*sizeof(step)); total_steps=n;calls=accepted=0;
    size_t sent=999; errno=0;
    assert(write_all_nb(123,data,10,&sent)==result); assert(sent==bytes);assert(calls==n);
    if(error) assert(errno==error);
}
int main(void) {
    scenario((step[]){{3,0},{-1,EINTR},{2,0},{5,0}},4,0,10,0);
    scenario((step[]){{3,0},{-1,EAGAIN}},2,1,3,EAGAIN);
    scenario((step[]){{-1,EWOULDBLOCK}},1,1,0,EWOULDBLOCK);
    scenario((step[]){{4,0},{-1,EBADF}},2,-1,4,EBADF);
    scenario((step[]){{2,0},{0,0}},2,-1,2,EIO);
    total_steps=calls=0;size_t sent=999;
    assert(write_all_nb(123,NULL,0,&sent)==0&&sent==0&&calls==0);
    assert(write_all_nb(123,NULL,1,&sent)==-1&&errno==EINVAL&&sent==0);
    assert(write_all_nb(123,data,1,NULL)==-1&&errno==EINVAL&&calls==0);
    int fds[2];assert(pipe(fds)==0);
    assert(fcntl(fds[1],F_SETFL,O_NONBLOCK)==0);
    char buffer[4096];memset(buffer,'x',sizeof buffer);
    while(write(fds[1],buffer,sizeof buffer)>0) {}
    assert(errno==EAGAIN||errno==EWOULDBLOCK);
    assert(real_write_all_nb(fds[1],data,10,&sent)==1&&sent==0);
    assert(fcntl(fds[0],F_SETFL,O_NONBLOCK)==0);
    while(read(fds[0],buffer,sizeof buffer)>0) {}
    assert(real_write_all_nb(fds[1],data,10,&sent)==0&&sent==10);
    assert(read(fds[0],buffer,sizeof buffer)==10&&memcmp(buffer,data,10)==0);
    assert(signal(SIGPIPE,SIG_IGN)!=SIG_ERR);close(fds[0]);
    assert(real_write_all_nb(fds[1],data,10,&sent)==-1&&errno==EPIPE&&sent==0);
    close(fds[1]);puts("POSIX partial writes/EINTR/EAGAIN/zero/error + real nonblocking pipe PASS");
}

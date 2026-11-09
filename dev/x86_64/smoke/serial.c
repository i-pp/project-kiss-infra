/*
 * SPDX-FileCopyrightText: 2026 I-plusplus Inc.
 * SPDX-License-Identifier: LicenseRef-KOL-v1
 */

// Validation-only 16550 COM1. No host I/O permission is requested.
#include "serial.h"
static void outb(uint16_t port,uint8_t value) { __asm__ volatile("outb %0,%1"::"a"(value),"Nd"(port)); }
static uint8_t inb(uint16_t port) { uint8_t v; __asm__ volatile("inb %1,%0":"=a"(v):"Nd"(port));return v; }
void serial_init(void) {
    outb(0x3f9,0); outb(0x3fb,0x80); outb(0x3f8,1); outb(0x3f9,0);
    outb(0x3fb,3); outb(0x3fa,0xc7); outb(0x3fc,0x0b);
}
void serial_puts(const char *s) {
    while (*s) { while (!(inb(0x3fd)&0x20)) {} outb(0x3f8,(uint8_t)*s++); }
}
void serial_u64(uint64_t v) {
    char buf[21];unsigned n=0;
    do {buf[n++]=(char)('0'+v%10);v/=10;}while(v);
    while(n) { char s[2]={buf[--n],0};serial_puts(s); }
}

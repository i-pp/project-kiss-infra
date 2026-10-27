"""Agent-authored controls validate the independent harness, never sent to the LLM."""
from pathlib import Path

sources={
'c_parse.c':r'''#include <stdint.h>
#include <stddef.h>
int parse_u32(const char*s,uint32_t*out){if(!s||!out||!*s)return 0;uint32_t v=0;for(;*s;++s){if(*s<'0'||*s>'9')return 0;uint32_t d=(uint32_t)(*s-'0');if(v>UINT32_MAX/10||(v==UINT32_MAX/10&&d>UINT32_MAX%10))return 0;v=v*10+d;}*out=v;return 1;}
''',
'cpp_alias.cpp':r'''#include <vector>
#include <cstdint>
#include <cstddef>
bool append_slice(std::vector<std::uint8_t>&v,std::size_t off,std::size_t len){if(off>v.size()||len>v.size()-off)return false;std::vector<std::uint8_t> copy(v.begin()+off,v.begin()+off+len);v.insert(v.end(),copy.begin(),copy.end());return true;}
''',
'posix_write.c':r'''#include <unistd.h>
#include <errno.h>
#include <stddef.h>
int write_all_nb(int fd,const void*buf,size_t len,size_t*sent){if(!sent){errno=EINVAL;return -1;}*sent=0;if(!buf&&len){errno=EINVAL;return -1;}while(*sent<len){ssize_t r=write(fd,(const char*)buf+*sent,len-*sent);if(r>0){*sent+=(size_t)r;continue;}if(r==0){errno=EIO;return -1;}if(errno==EINTR)continue;if(errno==EAGAIN||errno==EWOULDBLOCK)return 1;return -1;}return 0;}
''',
'rust_prefix.rs':r'''pub fn prefix_sums(xs:&[i32])->Option<Vec<i32>>{let mut sum=0_i32;let mut out=Vec::new();for &x in xs{sum=sum.checked_add(x)?;out.push(sum);}Some(out)}
''',
'aarch64_sum.S':r'''.text
.global sum_u32
.type sum_u32,%function
sum_u32:
mov x2,x0
mov x0,#0
cbz x1,2f
1: ldr w3,[x2],#4
add x0,x0,x3
subs x1,x1,#1
b.ne 1b
2: ret
.size sum_u32,.-sum_u32
.section .note.GNU-stack,"",%progbits
''',
'neon_sad.c':r'''#include <arm_neon.h>
#include <stddef.h>
#include <stdint.h>
uint64_t sad_u8_neon(const uint8_t*a,const uint8_t*b,size_t n){uint64_t s=0;size_t i=0;for(;i+16<=n;i+=16)s+=vaddlvq_u8(vabdq_u8(vld1q_u8(a+i),vld1q_u8(b+i)));for(;i<n;++i){int d=(int)a[i]-(int)b[i];s+=(uint64_t)(d<0?-d:d);}return s;}
''',
'neon_dot.c':r'''#include <arm_neon.h>
#include <stddef.h>
#include <stdint.h>
int64_t dot_i8_neon(const int8_t*a,const int8_t*b,size_t n){int64_t s=0;size_t i=0;for(;i+16<=n;i+=16){int8x16_t x=vld1q_s8(a+i),y=vld1q_s8(b+i);s+=(int64_t)vaddlvq_s16(vmull_s8(vget_low_s8(x),vget_low_s8(y)));s+=(int64_t)vaddlvq_s16(vmull_s8(vget_high_s8(x),vget_high_s8(y)));}for(;i<n;++i)s+=(int64_t)a[i]*(int64_t)b[i];return s;}
'''}
positive=Path('logs/coder/control-positive');negative=Path('logs/coder/control-negative')
positive.mkdir(parents=True,exist_ok=False);negative.mkdir(parents=True,exist_ok=False)
for name,source in sources.items():
    (positive/name).write_text(source)
    (negative/name).write_text(source)
# Selected deliberately broken implementations must be rejected.
(negative/'c_parse.c').write_text(sources['c_parse.c'].replace("if(*s<'0'||*s>'9')return 0;", "if(*s=='x')return 1;if(*s<'0'||*s>'9')return 0;"))
(negative/'cpp_alias.cpp').write_text(sources['cpp_alias.cpp'].replace('std::vector<std::uint8_t> copy(v.begin()+off,v.begin()+off+len);v.insert(v.end(),copy.begin(),copy.end());','v.insert(v.end(),v.begin()+off,v.begin()+off+len);'))
(negative/'posix_write.c').write_text(sources['posix_write.c'].replace('if(errno==EINTR)continue;','if(errno==EINTR)return 1;'))
(negative/'rust_prefix.rs').write_text(sources['rust_prefix.rs'].replace('sum.checked_add(x)?','sum.wrapping_add(x)'))
(negative/'aarch64_sum.S').write_text(sources['aarch64_sum.S'].replace('mov x2,x0','mov x19,#999\nmov x2,x0'))
(negative/'neon_sad.c').write_text(sources['neon_sad.c'].replace('vaddlvq_u8(vabdq_u8(vld1q_u8(a+i),vld1q_u8(b+i)))','vaddvq_u8(vabdq_u8(vld1q_u8(a+i),vld1q_u8(b+i)))'))
(negative/'neon_dot.c').write_text(sources['neon_dot.c'].replace('int64_t s=0;','int16_t s=0;'))

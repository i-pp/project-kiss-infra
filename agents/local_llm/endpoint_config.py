"""Owner-verified fixed router route. No HTTP, DNS, Docker or process execution."""
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import uuid

IMAGE = 'sha256:0b332e21bec106548887f5747c0574bce63b8dd725f26d20382ff2711993ab15'
NETWORK = 'project-kiss-large-coder-b3_local'
RFC1918 = tuple(ipaddress.ip_network(n) for n in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16'))
CONTRACT = {'memory':34359738368,'memory_swap':34359738368,'cpu':8000000000,'pids':512,
            'readonly':True,'nonroot':True,'cap_drop_all':True,'no_new_privileges':True,
            'internal_network':True,'no_docker_socket':True,'fixed_internal_ipv4':True}
FIELDS = {'schema','mode','human_deployment_confirmed','image','container_id','deployment_token',
          'network_name','network_id','subnet','ipv4','port','endpoint_id','registry_sha256',
          'original_fingerprint','checked_at','contract'}
BLOCKED_PHASES = {'STOP_ORIGINAL_INTENT','ORIGINAL_STOPPED','START_ROUTER_INTENT','DEPLOYED',
                  'ROLLBACK_INTENT','ROLLBACK_FAILED','FAILED'}


class EndpointError(ValueError): pass


def object_pairs(pairs):
    result={}
    for k,v in pairs:
        if k in result:raise EndpointError('Duplicate metadata key')
        result[k]=v
    return result


def private_json(path):
    path=Path(path);root=path.parent
    if any(p.is_symlink() for p in [root,*root.parents]):raise EndpointError('Symlink route ancestry')
    s=root.lstat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.getuid() or stat.S_IMODE(s.st_mode)!=0o700:
        raise EndpointError('Owner-only route directory required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        s=os.fstat(fd)
        if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or stat.S_IMODE(s.st_mode)!=0o600 or s.st_nlink!=1 or s.st_size>16384:
            raise EndpointError('Unsafe route metadata')
        with os.fdopen(fd,'r') as stream:
            fd=None;data=json.load(stream,object_pairs_hook=object_pairs)
        if not isinstance(data,dict):raise EndpointError('Route metadata must be an object')
        return data
    finally:
        if fd is not None:os.close(fd)


def digest(runtime):
    return hashlib.sha256((Path(runtime).parent/'model_registry.json').read_bytes()).hexdigest()


def validate_receipt(data,runtime,candidate=False,phase_check=True):
    root=Path(runtime)
    profile=private_json(root/'router-host-profile.json')
    state=private_json(root/'router-host-state.json')
    if set(data)!=FIELDS or type(data.get('schema')) is not int or data['schema']!=2 or data.get('mode')!='router':
        raise EndpointError('Unknown route schema')
    if data.get('human_deployment_confirmed') is not (not candidate):raise EndpointError('Unconfirmed route')
    if type(data.get('port')) is not int or data['port']!=8080:raise EndpointError('Fixed port only')
    contract=data.get('contract')
    if (data.get('image')!=IMAGE or profile.get('image')!=IMAGE or not isinstance(contract,dict) or
        set(contract)!=set(CONTRACT) or any(type(contract[k]) is not type(v) or contract[k]!=v for k,v in CONTRACT.items())):
        raise EndpointError('Route image or protection contract differs')
    for k in ('container_id','network_id','endpoint_id','registry_sha256','original_fingerprint'):
        if not isinstance(data.get(k),str) or re.fullmatch('[0-9a-f]{64}',data[k]) is None:
            raise EndpointError('Incomplete route identity')
    if (data['container_id']!=state.get('router_cid') or data['deployment_token']!=state.get('token') or
        re.fullmatch('[0-9a-f]{32}',str(data['deployment_token'])) is None or
        data['original_fingerprint']!=state.get('original_fingerprint') or
        state.get('resident_cid')!=profile.get('resident_container_id') or
        data['network_name']!=NETWORK or profile.get('existing_internal_network')!=NETWORK or
        data['network_id']!=profile.get('internal_network_id') or
        data['ipv4']!=state.get('route_ipv4') or data['subnet']!=state.get('route_subnet') or
        data['network_id']!=state.get('route_network_id') or data['endpoint_id']!=state.get('route_endpoint_id') or
        data['registry_sha256']!=digest(root)):
        raise EndpointError('Route identity is stale or differs from approved host state')
    if phase_check and state.get('phase') not in ({'START_ROUTER_INTENT','DEPLOYED'} if candidate else {'DEPLOYED'}):
        raise EndpointError('Router is not in a usable deployment phase')
    if type(data.get('checked_at')) not in (int,float) or not 0<data['checked_at']<10**11:
        raise EndpointError('Invalid route timestamp')
    try:
        address=ipaddress.IPv4Address(data['ipv4']);network=ipaddress.IPv4Network(data['subnet'],strict=True)
    except (ValueError,TypeError) as exc:raise EndpointError('Literal private IPv4 required') from exc
    if (str(address)!=data['ipv4'] or str(network)!=data['subnet'] or
        not any(network.subnet_of(n) for n in RFC1918) or address not in network or
        address in (network.network_address,network.broadcast_address)):
        raise EndpointError('Route is outside the verified private subnet')
    return data


def route(runtime,candidate=False,resident=False):
    root=Path(runtime)
    if resident:return {'mode':'resident','ipv4':'127.0.0.1','port':8080}
    p=root/('router-candidate.json' if candidate else 'router-deployment.json')
    # lexists catches broken symlinks instead of silently choosing localhost.
    if os.path.lexists(p):return validate_receipt(private_json(p),root,candidate=candidate)
    if candidate:raise EndpointError('Verified router candidate is missing')
    state=root/'router-host-state.json'
    if os.path.lexists(state) and private_json(state).get('phase') in BLOCKED_PHASES:
        raise EndpointError('Router route absent during deployment or uncertain recovery')
    return {'mode':'resident','ipv4':'127.0.0.1','port':8080}


def atomic_private(path,data):
    path=Path(path)
    if os.path.lexists(path):private_json(path)
    temp=path.parent/('route-'+uuid.uuid4().hex+'.tmp')
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'w') as stream:
            json.dump(data,stream);stream.flush();os.fsync(stream.fileno())
        os.replace(temp,path)
    finally:
        if temp.exists():temp.unlink()

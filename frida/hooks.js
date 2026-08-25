'use strict';
// QQMusic .mgg (musicex + QMC2) ekey / cipher capture
// Architecture-aware: arm64 (native on Apple Silicon) or x64 (Rosetta)

var ADDRS;
if (Process.arch === 'arm64') {
    ADDRS = {
        initWithEKey:   0x1000f6d0c,  // -[QMStreamEncrypt initWithEKey:]
        streamDecrypt:  0x1000f6f34,  // -[QMStreamEncrypt streamDecrypt:offset:size:]
        setEkey:        0x1001751d4,  // -[QMSongInfo setEkeyWithSongRateType:ekey:]
        vkeyForSong:    0x10056116c,  // -[? vkeyForSpecificSong:songRate:listen:]
    };
} else {
    ADDRS = {
        initWithEKey:   0x1001355f1,
        streamDecrypt:  0x10013583f,
        setEkey:        0x1001d3a02,
        vkeyForSong:    0x1006cc3af,
    };
}

function log(m){ console.log('[qmgg] ' + m); }

function toStr(p){
    try { return ObjC.Object(p).toString(); } catch(e){ return '<obj ' + p + '>'; }
}
function hex(buf, n){
    try {
        var o=[]; for(var i=0;i<n && i<buf.length;i++) o.push(('0'+buf[i].toString(16)).slice(-2));
        return o.join(' ');
    } catch(e){ return 'err'; }
}

function readCipherState(selfPtr){
    // QMStreamEncrypt._streamEncryptAndDecrypt @ +8  -> StreamEncAndDec*
    // StreamEncAndDec: +0x08 table ptr, +0x10 N (int32), +0x60 S-box ptr
    try {
        var streamObj = selfPtr.add(8).readPointer();
        if (streamObj.isNull()) return {N: -1, note: 'streamObj NULL'};
        var N = streamObj.add(0x10).readS32();
        var table = streamObj.add(0x8).readPointer();
        var sbox  = streamObj.add(0x60).readPointer();
        var path = N >= 301 ? 'RC4 (EncFirstSegment+EncASegment)' : (N > 0 ? 'mapL (per-byte)' : 'no-op');
        return {
            N: N, path: path,
            table: table.isNull()?null:table.toString(16),
            table16: table.isNull()?null:hex(Memory.readByteArray(table,16),16),
            sbox: sbox.isNull()?null:sbox.toString(16),
            sbox16: sbox.isNull()?null:hex(Memory.readByteArray(sbox,16),16),
        };
    } catch(e){ return {N:-2, note:String(e)}; }
}

// 1) -[QMStreamEncrypt initWithEKey:]  -> capture ekey + cipher state (N)
Interceptor.attach(ptr(ADDRS.initWithEKey), {
    onEnter(args){
        this.self = args[0];
        try { this.ekey = toStr(args[2]); } catch(e){ this.ekey = '<err>'; }
    },
    onLeave(){
        var st = readCipherState(this.self);
        var rec = { type:'initWithEKey', ekey:this.ekey,
                    ekeyLen: this.ekey?this.ekey.length:-1,
                    N: st.N, path: st.path||'', table: st.table, table16: st.table16,
                    sbox: st.sbox, sbox16: st.sbox16, note: st.note||'' };
        log('initWithEKey: len=' + rec.ekeyLen + ' N=' + rec.N + '  =>  ' + rec.path);
        send(rec);
    }
});

// 2) -[QMSongInfo setEkeyWithSongRateType:ekey:]  -> rateType + ekey
Interceptor.attach(ptr(ADDRS.setEkey), {
    onEnter(args){
        try {
            var rateType = args[2].toInt32();
            var ekey = toStr(args[3]);
            log('setEkey: rateType=' + rateType + '  ekeyLen=' + ekey.length);
            send({ type:'setEkey', rateType: rateType, ekey: ekey, ekeyLen: ekey.length });
        } catch(e){ log('setEkey err=' + e); }
    }
});

// 3) vkeyForSpecificSong:songRate:listen:  -> VkeyData source
Interceptor.attach(ptr(ADDRS.vkeyForSong), {
    onLeave(retval){
        try {
            var v = ObjC.Object(retval);
            var ekey = (v.ekey && v.ekey()) ? v.ekey().toString() : '<nil>';
            var valid = (v.isEkeyValid) ? v.isEkeyValid() : null;
            var exp = (v.expirationTime) ? v.expirationTime() : null;
            log('vkeyForSong: ekeyLen=' + ekey.length + ' valid=' + valid);
            send({ type:'vkey', ekey:ekey, ekeyLen:ekey.length, valid:valid,
                   expiration: exp?exp.toString():null });
        } catch(e){ log('vkeyForSong err=' + e); }
    }
});

// 4) -[QMStreamEncrypt streamDecrypt:offset:size:]  -> verify: buffer before/after
var decCount = 0;
Interceptor.attach(ptr(ADDRS.streamDecrypt), {
    onEnter(args){
        this.buf = args[2]; this.offset = args[3].toInt64(); this.size = args[4].toInt32();
        if (decCount < 8 && this.size > 0){
            try { this.before = hex(Memory.readByteArray(this.buf, Math.min(32,this.size)), Math.min(32,this.size)); }
            catch(e){ this.before='err'; }
        }
    },
    onLeave(){
        if (decCount < 8){
            decCount++;
            try {
                var after = hex(Memory.readByteArray(this.buf, Math.min(32,this.size)), Math.min(32,this.size));
                log('streamDecrypt #' + decCount + ' offset=' + this.offset + ' size=' + this.size);
                log('   before: ' + this.before);
                log('   after : ' + after);
                send({ type:'decrypt', n:decCount, offset:this.offset.toString(), size:this.size, before:this.before, after:after });
            } catch(e){}
        }
    }
});

log('hooks installed (arch=' + Process.arch + ')');

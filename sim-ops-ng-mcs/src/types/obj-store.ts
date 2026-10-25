// Object-store payloads served by the API's /api/obj-store/* routes (so/api.py)

// a pass's flight-dynamics product, as SimOps stores it (so/core.py)
export interface FDProduct {
  id: string
  status: number
  validity: number
  data: unknown[][]
}

// a TM/TC bucket and its object names (GET /api/obj-store/tm)
export interface Bucket {
  bucket: string
  data: string[]
}

// a decoded space packet (GET /api/obj-store/sp/..., SpacePacketHandler.as_dict in so/utils.py)
export interface SpacePacket {
  primary_header: Record<string, string | number>
  sec_hdr: null
  // TC: command and value; TM: the unpacked telemetry fields
  payload: Record<string, string | number | boolean>
}

use http_body_util::BodyExt;
use rand::prelude::IndexedRandom;
use serde_json::{Value, json};
use vercel_runtime::{Error, Request, Response, ResponseBody, run, service_fn};

#[tokio::main]
async fn main() -> Result<(), Error> {
    let service = service_fn(handler);
    run(service).await
}
pub async fn handler(req: Request) -> Result<Response<ResponseBody>, Error> {
    // Only accept requests targeting the /build path
    let path = req.uri().path().to_string();
    println!("Received request for path: {}", path);
    if path == "/api/pattern-generator/build" {
        return handler_build(req).await;
    } else if path == "/api/pattern-generator/view/V0" {
        return handler_view_v0(req).await;
    } else if path == "/api/pattern-generator/view/V1" {
        return handler_view_v1(req).await;
    } else if path == "/api/pattern-generator/view/V2" {
        return handler_view_v2(req).await;
    } else if path == "/api/pattern-generator/view/V3" {
        return handler_view_v3(req).await;
    } else if path == "/api/pattern-generator/view/V4" {
        return handler_view_v4(req).await;
    }
        return Ok(Response::builder()
            .status(404)
            .header("Content-Type", "text/plain")
            .body(ResponseBody::from("not found"))?);

}
pub async fn handler_build(req: Request) -> Result<Response<ResponseBody>, Error> {
    let (_, body) = req.into_parts();
    let body_bytes = body.collect().await?.to_bytes();
    let body: Value = serde_json::from_slice(&body_bytes).unwrap_or(json!({}));
    match body["version"].as_str().unwrap_or("") {
        "V0" => handler_build_v0(body).await,
        "V1" => handler_build_v1(body).await,
        "V2" => handler_build_v2(body).await,
        "V3" => handler_build_v3(body).await,
        "V4" => handler_build_v4(body).await,
        _ => Ok(Response::builder()
        .status(400)
        .header("Content-Type", "text/plain")
        .body(ResponseBody::from("bad request"))?),
    }
}
pub async fn handler_view_v0(req: Request) -> Result<Response<ResponseBody>, Error> {
    // Expect incoming shape { "a": leds, "b": [ { "a": [colors], "b": delay }, ... ] }
    // Transform to { "leds": ..., "rows": [ { "colors": ..., "delay": ... }, ... ] }
    let (_, body) = req.into_parts();
    let body_bytes = body.collect().await?.to_bytes();
    let mut body: Value = serde_json::from_slice(&body_bytes).unwrap_or(json!({}));
    if let Value::Object(map) = &mut body {
        map.remove("version");
        if let Some(v) = map.remove("a") {
            map.insert("leds".to_string(), v);
        }
        if let Some(rows_val) = map.remove("b") {
            let new_rows = match rows_val {
                Value::Array(arr) => {
                    let transformed: Vec<Value> = arr
                        .into_iter()
                        .map(|row| {
                            match row {
                                Value::Object(mut rmap) => {
                                    if let Some(c) = rmap.remove("a") {
                                        rmap.insert("colors".to_string(), c);
                                    }
                                    if let Some(d) = rmap.remove("b") {
                                        rmap.insert("delay".to_string(), d);
                                    }
                                    Value::Object(rmap)
                                }
                                other => other,
                            }
                        })
                        .collect();
                    Value::Array(transformed)
                }
                other => other,
            };
            map.insert("rows".to_string(), new_rows);
        }
    }

    // Return the modified JSON as the response body
    let body = serde_json::to_string(&body).unwrap_or_else(|_| "{}".to_string());
    println!("body={}", body);
    Ok(Response::builder()
        .status(200)
        .header("Content-Type", "application/json")
        .body(ResponseBody::from(body))?)
}
pub async fn handler_build_v0(mut req: Value) -> Result<Response<ResponseBody>, Error> {
    // Rename top-level "rows" -> "b", and inside each row rename "colors" -> "a", "delay" -> "b"
    if let Value::Object(map) = &mut req {
        map.remove("version");
        if let Some(v) = map.remove("leds") {
            map.insert("a".to_string(), v);
        }
        if let Some(rows_val) = map.remove("rows") {
            let new_rows = match rows_val {
                Value::Array(arr) => {
                    let transformed: Vec<Value> = arr
                        .into_iter()
                        .map(|row| {
                            match row {
                                Value::Object(mut rmap) => {
                                    if let Some(c) = rmap.remove("colors") {
                                        rmap.insert("a".to_string(), c);
                                    }
                                    if let Some(d) = rmap.remove("delay") {
                                        rmap.insert("b".to_string(), d);
                                    }
                                    Value::Object(rmap)
                                }
                                other => other,
                            }
                        })
                        .collect();
                    Value::Array(transformed)
                }
                other => other,
            };
            map.insert("b".to_string(), new_rows);
        }
    }

    // Return the modified JSON as the response body
    let body = serde_json::to_string(&req).unwrap_or_else(|_| "{}".to_string());
    println!("body={}", body);
    Ok(Response::builder()
        .status(200)
        .header("Content-Type", "application/json")
        .body(ResponseBody::from(body))?)
}
pub async fn handler_view_v1(req: Request) -> Result<Response<ResponseBody>, Error> {
    let (_, body) = req.into_parts();
    let body_bytes = body.collect().await?.to_bytes();
    println!("handler_view_v1 received body bytes: {:02X?}", body_bytes);

    // Expect binary format produced by handler_build_v1:
    // [4 bytes leds (u32 BE)] [for each row: leds*3 bytes RGB triplets][4 bytes delay (u32 BE)] ...
    if body_bytes.len() < 4 {
        return Ok(Response::builder()
            .status(400)
            .header("Content-Type", "text/plain")
            .body(ResponseBody::from("invalid body"))?);
    }

    let mut offset: usize = 0;
    let mut arr4: [u8; 4] = [0; 4];
    arr4.copy_from_slice(&body_bytes[0..4]);
    let leds = u32::from_be_bytes(arr4) as usize;
    offset += 4;

    let mut rows: Vec<Value> = Vec::new();
    while offset + leds * 3 + 4 <= body_bytes.len() {
        // read leds RGB triplets
        let mut colors: Vec<Value> = Vec::with_capacity(leds);
        for _ in 0..leds {
            let r = body_bytes[offset] as u32;
            let g = body_bytes[offset + 1] as u32;
            let b = body_bytes[offset + 2] as u32;
            offset += 3;
            let rgb = (r << 16) | (g << 8) | b;
            colors.push(Value::from(rgb));
        }
        // read delay
        let mut darr: [u8; 4] = [0; 4];
        darr.copy_from_slice(&body_bytes[offset..offset + 4]);
        offset += 4;
        let delay = u32::from_be_bytes(darr);

        rows.push(json!({"colors": colors, "delay": delay}));
    }

    let resp = json!({ "leds": leds, "rows": rows });
    let body = serde_json::to_string(&resp).unwrap_or_else(|_| "{}".to_string());
    println!("handler_view_v1 parsed rows={}, leds={}", rows.len(), leds);
    Ok(Response::builder()
        .status(200)
        .header("Content-Type", "application/json")
        .body(ResponseBody::from(body))?)
}
pub async fn handler_build_v1(mut body: Value) -> Result<Response<ResponseBody>, Error> {
    let mut bytes: Vec<u8> = Vec::new();
    println!("body={}", body);
    let leds = body["leds"].as_u64().unwrap_or(0);
    bytes.extend_from_slice(&(leds as u32).to_be_bytes());
    if let Value::Array(rows) = &body["rows"] {
        for (i, row) in rows.iter().enumerate() {
            let delay = row["delay"].as_u64().unwrap_or(0);
            for color in row["colors"].as_array().unwrap_or(&vec![]) {
                let c = color.as_u64().unwrap_or(0) as u32;
                let b = c.to_be_bytes();
                bytes.extend_from_slice(&b[1..]);
            }
            bytes.extend_from_slice(&(delay as u32).to_be_bytes());
        }
    }
    println!("leds={}, bytes=[{:02X?}]", leds, bytes);
    Ok(Response::builder()
        .status(200)
        .header("Content-Type", "application/octet-stream")
        .header("Content-Disposition", "attachment; filename=\"pattern.bin\"")
        .body(ResponseBody::from(bytes))?)
}
pub async fn handler_build_v2(body: Value) -> Result<Response<ResponseBody>, Error> {
    let mut bytes: Vec<u8> = Vec::new();
    let leds = body["leds"].as_u64().unwrap_or(0) as u32;
    let rows = body["rows"].as_array();
    let num_frames = rows.map(|r| r.len()).unwrap_or(0) as u32;

    // Header: [4B leds][4B num_frames]
    bytes.extend_from_slice(&leds.to_be_bytes());
    bytes.extend_from_slice(&num_frames.to_be_bytes());

    if let Some(rows) = rows {
        for (i, row) in rows.iter().enumerate() {
            let delay = row["delay"].as_u64().unwrap_or(0) as u32;
            let colors: Vec<u32> = row["colors"]
                .as_array()
                .map(|arr| arr.iter().filter_map(|v| v.as_u64().map(|n| n as u32)).collect())
                .unwrap_or_default();

            // Convert to RGB triplets
            let triplets: Vec<[u8; 3]> = colors.iter()
                .map(|c| { let b = c.to_be_bytes(); [b[1], b[2], b[3]] })
                .collect();

            // RLE encode: [1B count][1B R][1B G][1B B] runs
            if !triplets.is_empty() {
                let mut current = triplets[0];
                let mut count: u8 = 1;
                for t in &triplets[1..] {
                    if *t == current && count < 255 {
                        count += 1;
                    } else {
                        bytes.push(count);
                        bytes.extend_from_slice(&current);
                        current = *t;
                        count = 1;
                    }
                }
                bytes.push(count);
                bytes.extend_from_slice(&current);
            }

            // [4B delay]
            bytes.extend_from_slice(&delay.to_be_bytes());
            println!("Row {}: delay={}", i, delay);
        }
    }

    println!("leds={}, frames={}, total bytes={}", leds, num_frames, bytes.len());
    Ok(Response::builder()
        .status(200)
        .header("Content-Type", "application/octet-stream")
        .header("Content-Disposition", "attachment; filename=\"pattern_rle.bin\"")
        .body(ResponseBody::from(bytes))?)
}
pub async fn handler_view_v2(req: Request) -> Result<Response<ResponseBody>, Error> {
    let (_, body) = req.into_parts();
    let body_bytes = body.collect().await?.to_bytes();

    // Expect RLE binary: [4B leds][4B num_frames] per frame: RLE runs [1B count][3B RGB]... [4B delay]
    if body_bytes.len() < 8 {
        return Ok(Response::builder()
            .status(400)
            .header("Content-Type", "text/plain")
            .body(ResponseBody::from("invalid body"))?);
    }

    let mut offset: usize = 0;
    let mut arr4: [u8; 4] = [0; 4];

    arr4.copy_from_slice(&body_bytes[offset..offset + 4]);
    let leds = u32::from_be_bytes(arr4) as usize;
    offset += 4;

    arr4.copy_from_slice(&body_bytes[offset..offset + 4]);
    let num_frames = u32::from_be_bytes(arr4) as usize;
    offset += 4;

    let mut rows: Vec<Value> = Vec::with_capacity(num_frames);
    for _ in 0..num_frames {
        // Decode RLE runs until we have `leds` pixels
        let mut colors: Vec<Value> = Vec::with_capacity(leds);
        while colors.len() < leds {
            if offset + 4 > body_bytes.len() {
                break;
            }
            let count = body_bytes[offset] as usize;
            let r = body_bytes[offset + 1] as u32;
            let g = body_bytes[offset + 2] as u32;
            let b = body_bytes[offset + 3] as u32;
            offset += 4;
            let rgb = (r << 16) | (g << 8) | b;
            for _ in 0..count {
                if colors.len() < leds {
                    colors.push(Value::from(rgb));
                }
            }
        }

        // Read delay
        if offset + 4 > body_bytes.len() {
            break;
        }
        arr4.copy_from_slice(&body_bytes[offset..offset + 4]);
        let delay = u32::from_be_bytes(arr4);
        offset += 4;

        rows.push(json!({"colors": colors, "delay": delay}));
    }

    let resp = json!({ "leds": leds, "rows": rows });
    let body = serde_json::to_string(&resp).unwrap_or_else(|_| "{}".to_string());
    println!("handler_view_v2 parsed frames={}, leds={}", rows.len(), leds);
    Ok(Response::builder()
        .status(200)
        .header("Content-Type", "application/json")
        .body(ResponseBody::from(body))?)
}
pub async fn handler_build_v3(body: Value) -> Result<Response<ResponseBody>, Error> {
    let mut bytes: Vec<u8> = Vec::new();
    let leds = body["leds"].as_u64().unwrap_or(0) as u32;
    let rows = body["rows"].as_array();
    let num_frames = rows.map(|r| r.len()).unwrap_or(0) as u32;

    // Parse all frames into Vec<Vec<[u8;3]>> triplets
    let all_frames: Vec<Vec<[u8; 3]>> = rows
        .map(|rs| {
            rs.iter()
                .map(|row| {
                    row["colors"]
                        .as_array()
                        .map(|arr| {
                            arr.iter()
                                .filter_map(|v| v.as_u64().map(|n| n as u32))
                                .map(|c| {
                                    let b = c.to_be_bytes();
                                    [b[1], b[2], b[3]]
                                })
                                .collect::<Vec<[u8; 3]>>()
                        })
                        .unwrap_or_default()
                })
                .collect()
        })
        .unwrap_or_default();

    // Build palette: collect unique RGB triplets, sorted
    let mut palette_set = std::collections::BTreeSet::new();
    for frame in &all_frames {
        for triplet in frame {
            palette_set.insert(*triplet);
        }
    }
    let palette: Vec<[u8; 3]> = palette_set.into_iter().collect();
    let mut palette_lookup = std::collections::HashMap::new();
    for (i, t) in palette.iter().enumerate() {
        palette_lookup.insert(*t, i as u8);
    }

    // Get constant delay from first row (or 0)
    let delay = rows
        .and_then(|rs| rs.first())
        .and_then(|r| r["delay"].as_u64())
        .unwrap_or(0) as u32;

    // --- HEADER ---
    // [4B leds][4B num_frames][4B delay][1B palette_len][palette_len*3B RGB]
    bytes.extend_from_slice(&leds.to_be_bytes());
    bytes.extend_from_slice(&num_frames.to_be_bytes());
    bytes.extend_from_slice(&delay.to_be_bytes());
    let pal_len = if palette.len() == 256 { 0u8 } else { palette.len() as u8 };
    bytes.push(pal_len);
    for t in &palette {
        bytes.extend_from_slice(t);
    }

    // --- KEYFRAME (frame 0) ---
    if let Some(first) = all_frames.first() {
        let indices: Vec<u8> = first
            .iter()
            .map(|t| *palette_lookup.get(t).unwrap_or(&0))
            .collect();
        // RLE encode palette indices: [1B count][1B index] runs
        let mut runs: Vec<(u8, u8)> = Vec::new();
        if !indices.is_empty() {
            let mut cur = indices[0];
            let mut count: u8 = 1;
            for &idx in &indices[1..] {
                if idx == cur && count < 255 {
                    count += 1;
                } else {
                    runs.push((count, cur));
                    cur = idx;
                    count = 1;
                }
            }
            runs.push((count, cur));
        }
        bytes.push(runs.len() as u8);
        for (count, idx) in &runs {
            bytes.push(*count);
            bytes.push(*idx);
        }

        // --- DELTA FRAMES ---
        let mut prev_indices = indices;
        for frame in &all_frames[1..] {
            let cur_indices: Vec<u8> = frame
                .iter()
                .map(|t| *palette_lookup.get(t).unwrap_or(&0))
                .collect();
            let mut changes: Vec<(u8, u8)> = Vec::new();
            for j in 0..leds as usize {
                if j < cur_indices.len()
                    && j < prev_indices.len()
                    && cur_indices[j] != prev_indices[j]
                {
                    changes.push((j as u8, cur_indices[j]));
                }
            }
            bytes.push(changes.len() as u8);
            for (led_idx, pal_idx) in &changes {
                bytes.push(*led_idx);
                bytes.push(*pal_idx);
            }
            prev_indices = cur_indices;
        }
    }

    println!(
        "v3 build: leds={}, frames={}, palette={}, total bytes={}",
        leds,
        num_frames,
        palette.len(),
        bytes.len()
    );
    Ok(Response::builder()
        .status(200)
        .header("Content-Type", "application/octet-stream")
        .header(
            "Content-Disposition",
            "attachment; filename=\"pattern_delta.bin\"",
        )
        .body(ResponseBody::from(bytes))?)
}
pub async fn handler_view_v3(req: Request) -> Result<Response<ResponseBody>, Error> {
    let (_, body) = req.into_parts();
    let body_bytes = body.collect().await?.to_bytes();

    // Expect delta+palette binary:
    // [4B leds][4B num_frames][4B delay][1B pal_len][pal_len*3B RGB]
    // keyframe: [1B num_runs][runs: 1B count, 1B idx]...
    // delta frames: [1B num_changes][changes: 1B led_idx, 1B pal_idx]...
    if body_bytes.len() < 13 {
        return Ok(Response::builder()
            .status(400)
            .header("Content-Type", "text/plain")
            .body(ResponseBody::from("invalid body"))?);
    }

    let mut offset: usize = 0;
    let mut arr4: [u8; 4] = [0; 4];

    arr4.copy_from_slice(&body_bytes[offset..offset + 4]);
    let leds = u32::from_be_bytes(arr4) as usize;
    offset += 4;

    arr4.copy_from_slice(&body_bytes[offset..offset + 4]);
    let num_frames = u32::from_be_bytes(arr4) as usize;
    offset += 4;

    arr4.copy_from_slice(&body_bytes[offset..offset + 4]);
    let delay = u32::from_be_bytes(arr4);
    offset += 4;

    let pal_len = {
        let v = body_bytes[offset] as usize;
        offset += 1;
        if v == 0 { 256 } else { v }
    };

    // Read palette
    let mut palette: Vec<u32> = Vec::with_capacity(pal_len);
    for _ in 0..pal_len {
        if offset + 3 > body_bytes.len() {
            break;
        }
        let r = body_bytes[offset] as u32;
        let g = body_bytes[offset + 1] as u32;
        let b = body_bytes[offset + 2] as u32;
        offset += 3;
        palette.push((r << 16) | (g << 8) | b);
    }

    let mut rows: Vec<Value> = Vec::with_capacity(num_frames);

    if num_frames == 0 {
        let resp = json!({ "leds": leds, "rows": rows });
        let body = serde_json::to_string(&resp).unwrap_or_else(|_| "{}".to_string());
        return Ok(Response::builder()
            .status(200)
            .header("Content-Type", "application/json")
            .body(ResponseBody::from(body))?);
    }

    // --- Decode keyframe ---
    let num_runs = body_bytes[offset] as usize;
    offset += 1;
    let mut fb: Vec<u8> = Vec::with_capacity(leds);
    for _ in 0..num_runs {
        if offset + 2 > body_bytes.len() {
            break;
        }
        let count = body_bytes[offset] as usize;
        let idx = body_bytes[offset + 1];
        offset += 2;
        for _ in 0..count {
            if fb.len() < leds {
                fb.push(idx);
            }
        }
    }

    // Emit keyframe row
    let colors: Vec<Value> = fb
        .iter()
        .map(|&idx| Value::from(*palette.get(idx as usize).unwrap_or(&0)))
        .collect();
    rows.push(json!({"colors": colors, "delay": delay}));

    // --- Decode delta frames ---
    for _ in 1..num_frames {
        if offset >= body_bytes.len() {
            break;
        }
        let num_changes = body_bytes[offset] as usize;
        offset += 1;
        for _ in 0..num_changes {
            if offset + 2 > body_bytes.len() {
                break;
            }
            let led_idx = body_bytes[offset] as usize;
            let pal_idx = body_bytes[offset + 1];
            offset += 2;
            if led_idx < fb.len() {
                fb[led_idx] = pal_idx;
            }
        }
        let colors: Vec<Value> = fb
            .iter()
            .map(|&idx| Value::from(*palette.get(idx as usize).unwrap_or(&0)))
            .collect();
        rows.push(json!({"colors": colors, "delay": delay}));
    }

    let resp = json!({ "leds": leds, "rows": rows });
    let body = serde_json::to_string(&resp).unwrap_or_else(|_| "{}".to_string());
    println!(
        "handler_view_v3 parsed frames={}, leds={}, palette={}",
        rows.len(),
        leds,
        pal_len
    );
    Ok(Response::builder()
        .status(200)
        .header("Content-Type", "application/json")
        .body(ResponseBody::from(body))?)
}
pub async fn handler_build_v4(body: Value) -> Result<Response<ResponseBody>, Error> {
    let mut bytes: Vec<u8> = Vec::new();
    let leds = body["leds"].as_u64().unwrap_or(0) as u32;
    let rows = body["rows"].as_array();
    let num_frames = rows.map(|r| r.len()).unwrap_or(0) as u32;

    // Parse all frames into RGB triplets
    let all_frames: Vec<Vec<[u8; 3]>> = rows
        .map(|rs| {
            rs.iter()
                .map(|row| {
                    row["colors"]
                        .as_array()
                        .map(|arr| {
                            arr.iter()
                                .filter_map(|v| v.as_u64().map(|n| n as u32))
                                .map(|c| {
                                    let b = c.to_be_bytes();
                                    [b[1], b[2], b[3]]
                                })
                                .collect::<Vec<[u8; 3]>>()
                        })
                        .unwrap_or_default()
                })
                .collect()
        })
        .unwrap_or_default();

    // Build sorted palette
    let mut palette_set = std::collections::BTreeSet::new();
    for frame in &all_frames {
        for triplet in frame {
            palette_set.insert(*triplet);
        }
    }
    let palette: Vec<[u8; 3]> = palette_set.into_iter().collect();
    let mut palette_lookup = std::collections::HashMap::new();
    for (i, t) in palette.iter().enumerate() {
        palette_lookup.insert(*t, i as u8);
    }

    // Constant delay from first row
    let delay = rows
        .and_then(|rs| rs.first())
        .and_then(|r| r["delay"].as_u64())
        .unwrap_or(0) as u32;

    // Convert frames to palette indices
    let index_frames: Vec<Vec<u8>> = all_frames
        .iter()
        .map(|frame| {
            frame
                .iter()
                .map(|t| *palette_lookup.get(t).unwrap_or(&0))
                .collect()
        })
        .collect();

    // Build segments: find runs of identical (positions, signs) delta patterns
    // Kernel is always 4 consecutive LEDs with signs ±1
    // flags 0 = [-1,-1,+1,+1], flags 1 = [+1,+1,-1,-1]
    let mut segments: Vec<(u8, u8, u8)> = Vec::new(); // (start_led, count, flags)

    if index_frames.len() > 1 {
        let mut prev = &index_frames[0];
        let mut cur_start: Option<u8> = None;
        let mut cur_flags: u8 = 0;
        let mut cur_count: u8 = 0;

        for frame in &index_frames[1..] {
            // Find changed positions
            let changes: Vec<usize> = (0..leds as usize)
                .filter(|&j| j < frame.len() && j < prev.len() && frame[j] != prev[j])
                .collect();

            // Determine start_led and flags
            let (start, flags) = if changes.len() == 4
                && changes == vec![changes[0], changes[0] + 1, changes[0] + 2, changes[0] + 3]
            {
                let signs: Vec<i8> = changes
                    .iter()
                    .map(|&j| if frame[j] > prev[j] { 1 } else { -1 })
                    .collect();
                if signs == vec![-1, -1, 1, 1] {
                    (changes[0] as u8, 0u8)
                } else {
                    (changes[0] as u8, 1u8)
                }
            } else {
                // Fallback: shouldn't happen for valid wave data
                (0u8, 0u8)
            };

            if cur_start == Some(start) && cur_flags == flags && cur_count < 255 {
                cur_count += 1;
            } else {
                if cur_start.is_some() {
                    segments.push((cur_start.unwrap(), cur_count, cur_flags));
                }
                cur_start = Some(start);
                cur_flags = flags;
                cur_count = 1;
            }
            prev = frame;
        }
        if cur_start.is_some() {
            segments.push((cur_start.unwrap(), cur_count, cur_flags));
        }
    }

    // --- HEADER ---
    // [4B leds][4B num_frames][4B delay][1B pal_len][pal_len*3B RGB]
    bytes.extend_from_slice(&leds.to_be_bytes());
    bytes.extend_from_slice(&num_frames.to_be_bytes());
    bytes.extend_from_slice(&delay.to_be_bytes());
    let pal_len = if palette.len() == 256 { 0u8 } else { palette.len() as u8 };
    bytes.push(pal_len);
    for t in &palette {
        bytes.extend_from_slice(t);
    }

    // --- KEYFRAME (RLE of palette indices) ---
    if let Some(first) = index_frames.first() {
        let mut runs: Vec<(u8, u8)> = Vec::new();
        if !first.is_empty() {
            let mut cur = first[0];
            let mut count: u8 = 1;
            for &idx in &first[1..] {
                if idx == cur && count < 255 {
                    count += 1;
                } else {
                    runs.push((count, cur));
                    cur = idx;
                    count = 1;
                }
            }
            runs.push((count, cur));
        }
        bytes.push(runs.len() as u8);
        for (count, idx) in &runs {
            bytes.push(*count);
            bytes.push(*idx);
        }
    }

    // --- SEGMENTS ---
    // [1B num_segments][per segment: 1B start_led, 1B repeat_count, 1B flags]
    bytes.push(segments.len() as u8);
    for (start, count, flags) in &segments {
        bytes.push(*start);
        bytes.push(*count);
        bytes.push(*flags);
    }

    println!(
        "v4 build: leds={}, frames={}, palette={}, segments={}, total bytes={}",
        leds,
        num_frames,
        palette.len(),
        segments.len(),
        bytes.len()
    );
    Ok(Response::builder()
        .status(200)
        .header("Content-Type", "application/octet-stream")
        .header(
            "Content-Disposition",
            "attachment; filename=\"pattern_seg.bin\"",
        )
        .body(ResponseBody::from(bytes))?)
}
pub async fn handler_view_v4(req: Request) -> Result<Response<ResponseBody>, Error> {
    let (_, body) = req.into_parts();
    let body_bytes = body.collect().await?.to_bytes();

    // Expect segment binary:
    // [4B leds][4B num_frames][4B delay][1B pal_len][pal_len*3B RGB]
    // keyframe: [1B num_runs][runs: 1B count, 1B idx]...
    // segments: [1B num_segments][per seg: 1B start_led, 1B repeat_count, 1B flags]
    if body_bytes.len() < 13 {
        return Ok(Response::builder()
            .status(400)
            .header("Content-Type", "text/plain")
            .body(ResponseBody::from("invalid body"))?);
    }

    let mut offset: usize = 0;
    let mut arr4: [u8; 4] = [0; 4];

    arr4.copy_from_slice(&body_bytes[offset..offset + 4]);
    let leds = u32::from_be_bytes(arr4) as usize;
    offset += 4;

    arr4.copy_from_slice(&body_bytes[offset..offset + 4]);
    let num_frames = u32::from_be_bytes(arr4) as usize;
    offset += 4;

    arr4.copy_from_slice(&body_bytes[offset..offset + 4]);
    let delay = u32::from_be_bytes(arr4);
    offset += 4;

    let pal_len = {
        let v = body_bytes[offset] as usize;
        offset += 1;
        if v == 0 { 256 } else { v }
    };

    // Read palette
    let mut palette: Vec<u32> = Vec::with_capacity(pal_len);
    for _ in 0..pal_len {
        if offset + 3 > body_bytes.len() {
            break;
        }
        let r = body_bytes[offset] as u32;
        let g = body_bytes[offset + 1] as u32;
        let b = body_bytes[offset + 2] as u32;
        offset += 3;
        palette.push((r << 16) | (g << 8) | b);
    }

    let mut rows: Vec<Value> = Vec::with_capacity(num_frames);

    if num_frames == 0 {
        let resp = json!({ "leds": leds, "rows": rows });
        let body = serde_json::to_string(&resp).unwrap_or_else(|_| "{}".to_string());
        return Ok(Response::builder()
            .status(200)
            .header("Content-Type", "application/json")
            .body(ResponseBody::from(body))?);
    }

    // --- Decode keyframe ---
    let num_runs = body_bytes[offset] as usize;
    offset += 1;
    let mut fb: Vec<i16> = Vec::with_capacity(leds);
    for _ in 0..num_runs {
        if offset + 2 > body_bytes.len() {
            break;
        }
        let count = body_bytes[offset] as usize;
        let idx = body_bytes[offset + 1] as i16;
        offset += 2;
        for _ in 0..count {
            if fb.len() < leds {
                fb.push(idx);
            }
        }
    }

    // Emit keyframe
    let colors: Vec<Value> = fb
        .iter()
        .map(|&idx| Value::from(*palette.get(idx as usize).unwrap_or(&0)))
        .collect();
    rows.push(json!({"colors": colors, "delay": delay}));

    // --- Decode segments ---
    let kernels: [[i16; 4]; 2] = [[-1, -1, 1, 1], [1, 1, -1, -1]];

    if offset >= body_bytes.len() {
        let resp = json!({ "leds": leds, "rows": rows });
        let body = serde_json::to_string(&resp).unwrap_or_else(|_| "{}".to_string());
        return Ok(Response::builder()
            .status(200)
            .header("Content-Type", "application/json")
            .body(ResponseBody::from(body))?);
    }

    let num_segments = body_bytes[offset] as usize;
    offset += 1;

    for _ in 0..num_segments {
        if offset + 3 > body_bytes.len() {
            break;
        }
        let start = body_bytes[offset] as usize;
        let count = body_bytes[offset + 1] as usize;
        let flags = body_bytes[offset + 2] as usize;
        offset += 3;

        let kernel = if flags < kernels.len() {
            kernels[flags]
        } else {
            kernels[0]
        };

        for _ in 0..count {
            for k in 0..4 {
                if start + k < fb.len() {
                    fb[start + k] += kernel[k];
                }
            }
            let colors: Vec<Value> = fb
                .iter()
                .map(|&idx| {
                    Value::from(*palette.get(idx.max(0) as usize).unwrap_or(&0))
                })
                .collect();
            rows.push(json!({"colors": colors, "delay": delay}));
        }
    }

    let resp = json!({ "leds": leds, "rows": rows });
    let body = serde_json::to_string(&resp).unwrap_or_else(|_| "{}".to_string());
    println!(
        "handler_view_v4 parsed frames={}, leds={}, palette={}, segments={}",
        rows.len(),
        leds,
        pal_len,
        num_segments
    );
    Ok(Response::builder()
        .status(200)
        .header("Content-Type", "application/json")
        .body(ResponseBody::from(body))?)
}
pub async fn handler1(req: Request) -> Result<Response<ResponseBody>, Error> {
    let (_, body) = req.into_parts();
    let body_bytes = body.collect().await?.to_bytes();
    let body: Value = serde_json::from_slice(&body_bytes).unwrap_or(json!({}));
    let mut bytes: Vec<u8> = Vec::new();
    let leds = body["leds"].as_u64().unwrap_or(0);
    bytes.extend_from_slice(&(leds as u32).to_be_bytes());
    if let Value::Array(rows) = &body["rows"] {
        for (i, row) in rows.iter().enumerate() {
            let delay = row["delay"].as_u64().unwrap_or(0);
            let colors: Vec<u32> = row["colors"]
                .as_array()
                .map(|arr| arr.iter().filter_map(|v| v.as_u64().map(|n| n as u32)).collect())
                .unwrap_or_default();
            // RLE encode RGB triplets
            let triplets: Vec<[u8; 3]> = colors.iter()
                .map(|c| { let b = c.to_be_bytes(); [b[1], b[2], b[3]] })
                .collect();
            let mut rle_data: Vec<u8> = Vec::new();
            if !triplets.is_empty() {
                let mut current = triplets[0];
                let mut count: u8 = 1;
                for t in &triplets[1..] {
                    if *t == current && count < 255 {
                        count += 1;
                    } else {
                        rle_data.push(count);
                        rle_data.extend_from_slice(&current);
                        current = *t;
                        count = 1;
                    }
                }
                rle_data.push(count);
                rle_data.extend_from_slice(&current);
            }
            bytes.extend_from_slice(&(rle_data.len() as u16).to_be_bytes());
            bytes.extend_from_slice(&rle_data);
            bytes.extend_from_slice(&(delay as u32).to_be_bytes());
            println!("Row {}: delay={}, rle_len={}", i, delay, rle_data.len());
        }
    }
    println!("leds={}, total bytes={}", leds, bytes.len());
    Ok(Response::builder()
        .status(200)
        .header("Content-Type", "application/octet-stream")
        .header("Content-Disposition", "attachment; filename=\"pattern.bin\"")
        .body(ResponseBody::from(bytes))?)
}

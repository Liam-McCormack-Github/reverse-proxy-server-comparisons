package com.proxy;

record AuthRequest(String client_id, String client_secret) {}

record AuthResponse(String master_token) {}

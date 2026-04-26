import 'dart:convert';

import 'package:http/http.dart' as http;

class ApiException implements Exception {
  ApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() =>
      'ApiException(statusCode: $statusCode, message: $message)';
}

class ApiClient {
  ApiClient({required this.baseUrl, required this.token});

  final String baseUrl;
  final String token;

  String get _normalizedToken {
    final trimmed = token.trim();
    if (trimmed.toLowerCase().startsWith('bearer ')) {
      return trimmed.substring(7).trim();
    }
    return trimmed;
  }

  Uri _uri(String path, [Map<String, dynamic>? query]) {
    final normalizedBase = baseUrl.endsWith('/') ? baseUrl : '$baseUrl/';
    return Uri.parse(normalizedBase).resolve(path).replace(
          queryParameters: query?.map((key, value) => MapEntry(key, '$value')),
        );
  }

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (_normalizedToken.isNotEmpty) 'Authorization': 'Bearer $_normalizedToken',
      };

  Future<Map<String, dynamic>> getJson(String path,
      {Map<String, dynamic>? query}) async {
    final response = await http.get(_uri(path, query), headers: _headers);
    return _decodeResponse(response);
  }

  Future<Map<String, dynamic>> postJson(
      String path, Map<String, dynamic> body) async {
    final response = await http.post(
      _uri(path),
      headers: _headers,
      body: jsonEncode(body),
    );
    return _decodeResponse(response);
  }

  Future<Map<String, dynamic>> multipartPost(
    String path, {
    required Map<String, String> fields,
    required String fileField,
    required String filePath,
    String? fileName,
  }) async {
    final request = http.MultipartRequest('POST', _uri(path));
    request.fields.addAll(fields);
    request.headers.addAll(
      _normalizedToken.isNotEmpty
          ? {'Authorization': 'Bearer $_normalizedToken'}
          : {},
    );
    request.files.add(
      await http.MultipartFile.fromPath(
        fileField,
        filePath,
        filename: fileName,
      ),
    );
    final streamed = await request.send();
    final response = await http.Response.fromStream(streamed);
    return _decodeResponse(response);
  }

  Map<String, dynamic> _decodeResponse(http.Response response) {
    final dynamic body =
        response.body.isEmpty ? <String, dynamic>{} : jsonDecode(response.body);

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return body is Map<String, dynamic>
          ? body
          : <String, dynamic>{'data': body};
    }

    final message = _extractErrorMessage(body);
    throw ApiException(message, statusCode: response.statusCode);
  }

  String _extractErrorMessage(dynamic body) {
    if (body is! Map<String, dynamic>) {
      return 'Request failed';
    }

    final message = body['message']?.toString().trim();
    if (message != null && message.isNotEmpty) {
      return message;
    }

    final detail = body['detail'];
    if (detail is String && detail.trim().isNotEmpty) {
      return detail.trim();
    }
    if (detail is List && detail.isNotEmpty) {
      final first = detail.first;
      if (first is Map<String, dynamic>) {
        final listMessage = first['msg']?.toString().trim();
        if (listMessage != null && listMessage.isNotEmpty) {
          return listMessage;
        }
      }
      final asText = first.toString().trim();
      if (asText.isNotEmpty) {
        return asText;
      }
    }

    return 'Request failed';
  }
}

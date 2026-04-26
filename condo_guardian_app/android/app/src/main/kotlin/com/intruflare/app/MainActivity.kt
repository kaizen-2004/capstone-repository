package com.intruflare.app

import android.app.DownloadManager
import android.content.Context
import android.net.Uri
import android.os.Environment
import android.speech.tts.TextToSpeech
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.embedding.android.FlutterActivity
import io.flutter.plugin.common.MethodChannel
import java.util.Locale

class MainActivity : FlutterActivity(), TextToSpeech.OnInitListener {
    private var tts: TextToSpeech? = null
    private var ttsReady = false
    private var pendingSpeech: String? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "intruflare/tts")
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "speak" -> {
                        val text = call.argument<String>("text")?.trim().orEmpty()
                        speak(text)
                        result.success(true)
                    }

                    "stop" -> {
                        stopSpeaking()
                        result.success(true)
                    }

                    else -> result.notImplemented()
                }
            }

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "intruflare/files")
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "downloadSnapshot" -> {
                        val url = call.argument<String>("url")?.trim().orEmpty()
                        if (url.isBlank()) {
                            result.error("invalid_url", "Snapshot URL is required.", null)
                            return@setMethodCallHandler
                        }

                        val rawFileName =
                            call.argument<String>("fileName")?.trim().orEmpty()
                        val fileName =
                            if (rawFileName.isBlank()) "snapshot_${System.currentTimeMillis()}.jpg" else rawFileName

                        val rawHeaders = call.argument<Map<String, Any?>>("headers")
                        val headers = mutableMapOf<String, String>()
                        rawHeaders?.forEach { (key, value) ->
                            val headerValue = value?.toString()?.trim().orEmpty()
                            if (key.isNotBlank() && headerValue.isNotBlank()) {
                                headers[key.trim()] = headerValue
                            }
                        }

                        try {
                            val downloadId = queueSnapshotDownload(
                                url = url,
                                fileName = fileName,
                                headers = headers,
                            )
                            result.success(downloadId)
                        } catch (error: Exception) {
                            result.error(
                                "download_failed",
                                error.message ?: "Unable to queue snapshot download.",
                                null,
                            )
                        }
                    }

                    else -> result.notImplemented()
                }
            }
    }

    private fun queueSnapshotDownload(
        url: String,
        fileName: String,
        headers: Map<String, String>,
    ): Long {
        val safeName = fileName.replace(Regex("[^A-Za-z0-9._-]"), "_")
        val request = DownloadManager.Request(Uri.parse(url)).apply {
            setTitle(safeName)
            setDescription("IntruFlare snapshot")
            setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            setAllowedOverMetered(true)
            setAllowedOverRoaming(true)
            setDestinationInExternalPublicDir(
                Environment.DIRECTORY_PICTURES,
                "IntruFlare/$safeName",
            )
            headers.forEach { (key, value) ->
                addRequestHeader(key, value)
            }
        }

        val downloadManager =
            getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
        return downloadManager.enqueue(request)
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            ttsReady = true
            tts?.language = Locale.US
            pendingSpeech?.let {
                speakInternal(it)
                pendingSpeech = null
            }
        } else {
            ttsReady = false
        }
    }

    private fun ensureTts() {
        if (tts == null) {
            tts = TextToSpeech(applicationContext, this)
        }
    }

    private fun speak(text: String) {
        if (text.isBlank()) {
            return
        }
        ensureTts()
        if (!ttsReady) {
            pendingSpeech = text
            return
        }
        speakInternal(text)
    }

    private fun speakInternal(text: String) {
        tts?.speak(
            text,
            TextToSpeech.QUEUE_FLUSH,
            null,
            "countdown_${System.currentTimeMillis()}"
        )
    }

    private fun stopSpeaking() {
        tts?.stop()
    }

    override fun onDestroy() {
        stopSpeaking()
        tts?.shutdown()
        tts = null
        ttsReady = false
        super.onDestroy()
    }
}

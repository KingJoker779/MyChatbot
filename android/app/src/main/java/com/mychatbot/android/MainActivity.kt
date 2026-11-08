package com.mychatbot.android

import android.graphics.Color
import android.os.Bundle
import android.text.InputType
import android.view.Gravity
import android.view.inputmethod.EditorInfo
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.lifecycle.lifecycleScope
import com.arm.aichat.AiChat
import com.arm.aichat.InferenceEngine
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.util.Locale

class MainActivity : AppCompatActivity() {
	private lateinit var statusText: TextView
	private lateinit var transcript: TextView
	private lateinit var transcriptScroll: ScrollView
	private lateinit var messageInput: EditText
	private lateinit var sendButton: Button
	private lateinit var setupButton: Button

	private var engine: InferenceEngine? = null
	private var modelReady = false
	private var busy = false

	override fun onCreate(savedInstanceState: Bundle?) {
		super.onCreate(savedInstanceState)
		buildChatScreen()
		setupButton.setOnClickListener { prepareLocalModel() }
		sendButton.setOnClickListener { sendMessage() }
		messageInput.setOnEditorActionListener { _, actionId, _ ->
			if (actionId == EditorInfo.IME_ACTION_SEND) {
				sendMessage()
				true
			} else {
				false
			}
		}
	}

	private fun buildChatScreen() {
		val background = Color.rgb(247, 247, 251)
		WindowCompat.setDecorFitsSystemWindows(window, false)
		WindowCompat.getInsetsController(window, window.decorView).apply {
			isAppearanceLightStatusBars = true
			isAppearanceLightNavigationBars = true
		}
		window.setSoftInputMode(android.view.WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE)

		val root = LinearLayout(this).apply {
			orientation = LinearLayout.VERTICAL
			setPadding(dp(18), dp(12), dp(18), dp(12))
			setBackgroundColor(background)
		}
		val title = TextView(this).apply {
			text = getString(R.string.app_name)
			textSize = 25f
			setTextColor(Color.rgb(28, 29, 42))
			setPadding(0, dp(8), 0, dp(4))
		}
		statusText = TextView(this).apply {
			text = "Download the local AI once. It uses about 533 MB; Wi-Fi is recommended."
			textSize = 14f
			setTextColor(Color.rgb(83, 86, 105))
			setPadding(0, dp(2), 0, dp(8))
		}
		setupButton = Button(this).apply {
			text = "Download AI model (~533 MB)"
		}
		transcriptScroll = ScrollView(this).apply {
			isFillViewport = true
			setBackgroundColor(Color.WHITE)
		}
		transcript = TextView(this).apply {
			text = "Hi! I can help with questions, explanations, writing, ideas, math, coding, and more."
			textSize = 16f
			setTextColor(Color.rgb(36, 38, 52))
			setPadding(dp(14), dp(14), dp(14), dp(14))
			setTextIsSelectable(true)
		}
		transcriptScroll.addView(
			transcript,
			android.widget.FrameLayout.LayoutParams(
				android.view.ViewGroup.LayoutParams.MATCH_PARENT,
				android.view.ViewGroup.LayoutParams.WRAP_CONTENT,
			),
		)

		messageInput = EditText(this).apply {
			hint = "Ask anything..."
			isEnabled = false
			inputType =
				InputType.TYPE_CLASS_TEXT or
					InputType.TYPE_TEXT_FLAG_MULTI_LINE or
					InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
			imeOptions = EditorInfo.IME_ACTION_SEND
			minLines = 1
			maxLines = 4
			setPadding(dp(12), dp(8), dp(12), dp(8))
		}
		sendButton = Button(this).apply {
			text = "Send"
			isEnabled = false
		}
		val composer = LinearLayout(this).apply {
			orientation = LinearLayout.HORIZONTAL
			gravity = Gravity.CENTER_VERTICAL
			addView(
				messageInput,
				LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f),
			)
			addView(
				sendButton,
				LinearLayout.LayoutParams(
					LinearLayout.LayoutParams.WRAP_CONTENT,
					LinearLayout.LayoutParams.WRAP_CONTENT,
				),
			)
		}

		root.addView(title)
		root.addView(statusText)
		root.addView(setupButton)
		root.addView(
			transcriptScroll,
			LinearLayout.LayoutParams(
				LinearLayout.LayoutParams.MATCH_PARENT,
				0,
				1f,
			).apply {
				topMargin = dp(8)
				bottomMargin = dp(8)
			},
		)
		root.addView(composer)
		ViewCompat.setOnApplyWindowInsetsListener(root) { view, windowInsets ->
			val systemBars = windowInsets.getInsets(WindowInsetsCompat.Type.systemBars())
			val ime = windowInsets.getInsets(WindowInsetsCompat.Type.ime())
			view.setPadding(
				dp(18),
				dp(12) + systemBars.top,
				dp(18),
				dp(12) + maxOf(systemBars.bottom, ime.bottom),
			)
			windowInsets
		}
		setContentView(root)
	}

	private fun prepareLocalModel() {
		if (busy || modelReady) return
		busy = true
		setupButton.isEnabled = false
		statusText.text = "Preparing the local AI model..."
		lifecycleScope.launch {
			try {
				val modelFile = withContext(Dispatchers.IO) {
					ensureModelDownloaded { downloaded, total ->
						withContext(Dispatchers.Main) {
							statusText.text =
								if (total > 0) {
									"Downloading local AI: ${downloaded * 100 / total}%"
								} else {
									"Downloading local AI model..."
								}
						}
					}
				}
				statusText.text = "Loading the AI model. This may take a little while..."
				val localEngine = withContext(Dispatchers.IO) {
					AiChat.getInferenceEngine(applicationContext)
				}
				val initialState = withTimeout(120_000) {
					localEngine.state.first {
						it is InferenceEngine.State.Initialized ||
							it is InferenceEngine.State.ModelReady ||
							it is InferenceEngine.State.Error
					}
				}
				if (initialState is InferenceEngine.State.Error) {
					throw initialState.exception
				}
				if (initialState is InferenceEngine.State.Initialized) {
					localEngine.loadModel(modelFile.absolutePath)
				}
				localEngine.setSystemPrompt(SYSTEM_PROMPT)
				engine = localEngine
				modelReady = true
				setupButton.isEnabled = false
				setupButton.text = "AI ready"
				messageInput.isEnabled = true
				sendButton.isEnabled = true
				statusText.text = "Ready. Chat runs on this phone; no internet is needed to answer."
			} catch (error: CancellationException) {
				throw error
			} catch (error: Exception) {
				statusText.text = "Couldn't prepare the AI: ${error.message ?: error.javaClass.simpleName}"
				setupButton.isEnabled = true
			} finally {
				busy = false
			}
		}
	}

	private suspend fun ensureModelDownloaded(onProgress: suspend (Long, Long) -> Unit): File {
		val coroutineContext = currentCoroutineContext()
		val modelDirectory = File(filesDir, "models")
		if (!modelDirectory.exists() && !modelDirectory.mkdirs()) {
			throw IOException("Couldn't create the model folder.")
		}
		val modelFile = File(modelDirectory, MODEL_NAME)
		if (modelFile.isFile) {
			if (modelFile.length() == MODEL_SIZE) {
				withContext(Dispatchers.Main) {
					statusText.text = "Checking the downloaded AI model..."
				}
				if (sha256(modelFile) == MODEL_SHA256) return modelFile
			}
			if (!modelFile.delete()) {
				throw IOException("The incomplete model file couldn't be removed.")
			}
		}

		val temporaryFile = File(modelDirectory, "$MODEL_NAME.download")
		try {
			val connection = URL(MODEL_URL).openConnection() as HttpURLConnection
			connection.connectTimeout = 30_000
			connection.readTimeout = 120_000
			connection.setRequestProperty("User-Agent", "MyChatbot-Android/1.0")
			try {
				if (connection.responseCode !in 200..299) {
					throw IOException("Model download failed (HTTP ${connection.responseCode}).")
				}
				val total = connection.contentLengthLong.takeIf { it > 0 } ?: MODEL_SIZE
				connection.inputStream.use { input ->
					FileOutputStream(temporaryFile).use { output ->
						val buffer = ByteArray(1024 * 1024)
						var downloaded = 0L
						while (true) {
							coroutineContext.ensureActive()
							val count = input.read(buffer)
							if (count < 0) break
							output.write(buffer, 0, count)
							downloaded += count
							onProgress(downloaded, total)
						}
						output.fd.sync()
					}
				}
			} finally {
				connection.disconnect()
			}
			if (temporaryFile.length() != MODEL_SIZE) {
				throw IOException("The model download was incomplete. Please try again.")
			}
			if (sha256(temporaryFile) != MODEL_SHA256) {
				throw IOException("The model download failed its integrity check.")
			}
			if (!temporaryFile.renameTo(modelFile)) {
				throw IOException("Couldn't save the downloaded model.")
			}
			return modelFile
		} catch (error: Exception) {
			temporaryFile.delete()
			throw error
		}
	}

	private fun sha256(file: File): String {
		val digest = MessageDigest.getInstance("SHA-256")
		file.inputStream().buffered().use { input ->
			val buffer = ByteArray(1024 * 1024)
			while (true) {
				val count = input.read(buffer)
				if (count < 0) break
				digest.update(buffer, 0, count)
			}
		}
		return digest.digest().joinToString("") { "%02x".format(Locale.ROOT, it) }
	}

	private fun sendMessage() {
		val question = messageInput.text.toString().trim()
		val localEngine = engine
		if (question.isEmpty() || localEngine == null || busy) return

		messageInput.text.clear()
		if (STANDALONE_GREETING.matches(question)) {
			transcript.append("\n\nYou: $question\n\nBot: Hey! How can I help?\n")
			scrollToBottom()
			return
		}
		val pingAnswer = answerPingTime(question)
		if (pingAnswer != null) {
			transcript.append("\n\nYou: $question\n\nBot: $pingAnswer\n")
			scrollToBottom()
			return
		}

		busy = true
		messageInput.isEnabled = false
		sendButton.isEnabled = false
		transcript.append("\n\nYou: $question\n\nBot: ")
		val answerStart = transcript.text.length
		transcript.append("Thinking...")
		scrollToBottom()
		statusText.text = "Thinking..."

		lifecycleScope.launch {
			var answerStarted = false
			try {
				val answerLength =
					if (DETAILED_REQUEST.containsMatchIn(question)) 384 else 192
				localEngine.sendUserPrompt(question, answerLength).collect { token ->
					if (!answerStarted) {
						transcript.text = transcript.text.substring(0, answerStart)
						answerStarted = true
					}
					transcript.append(token)
					scrollToBottom()
				}
				if (!answerStarted) {
					transcript.text =
						transcript.text.substring(0, answerStart) + "(No response generated.)"
				}
				transcript.append("\n")
			} catch (error: CancellationException) {
				throw error
			} catch (error: Exception) {
				if (!answerStarted) {
					transcript.text = transcript.text.substring(0, answerStart)
				}
				transcript.append("[Reply failed: ${error.message ?: error.javaClass.simpleName}]")
			} finally {
				busy = false
				messageInput.isEnabled = modelReady
				sendButton.isEnabled = modelReady
				statusText.text =
					if (modelReady) "Ready. Chat runs locally on this phone."
					else "The local AI model isn't ready yet."
				scrollToBottom()
			}
		}
	}

	private fun scrollToBottom() {
		transcriptScroll.post { transcriptScroll.fullScroll(ScrollView.FOCUS_DOWN) }
	}

	private fun answerPingTime(question: String): String? {
		if (!PING_CONTEXT.containsMatchIn(question)) return null
		val match = PING_VALUE.find(question) ?: return null
		val value = match.groupValues[1].replace(",", "").toDoubleOrNull() ?: return null
		val milliseconds = value * if (match.groupValues[2].isNotEmpty()) 1000 else 1
		if (!milliseconds.isFinite() || milliseconds > MAX_PING_MILLISECONDS) return null

		val seconds = milliseconds / 1000
		val totalSeconds = kotlin.math.round(seconds).toLong()
		val minutes = totalSeconds / 60
		val remainingSeconds = totalSeconds % 60
		val minuteText =
			if (minutes == 0L) "" else " (${minutes} minute${if (minutes == 1L) "" else "s"} " +
				"$remainingSeconds second${if (remainingSeconds == 1L) "" else "s"})"
		val secondsText = seconds.toString().removeSuffix(".0")
		val millisecondsText = String.format(Locale.US, "%,.0f", milliseconds)

		return "$millisecondsText ms is $secondsText seconds$minuteText. That is extremely high ping."
	}

	private fun dp(value: Int): Int =
		(value * resources.displayMetrics.density).toInt()

	companion object {
		private const val MODEL_NAME = "Qwen3.5-0.8B-Q4_K_M.gguf"
		private const val MODEL_SIZE = 532_517_120L
		private const val MODEL_SHA256 =
			"bd258782e35f7f458f8aced1adc053e6e92e89bc735ba3be89d38a06121dc517"
		private const val MODEL_URL =
			"https://huggingface.co/unsloth/Qwen3.5-0.8B-GGUF/resolve/main/" +
				"Qwen3.5-0.8B-Q4_K_M.gguf?download=true"
		private val DETAILED_REQUEST = Regex(
			"""(?i)\b(explain|details?|steps?|examples?|compare|thorough|in depth|write|create|story|essay|code|program|how to)\b""",
		)
		private val STANDALONE_GREETING = Regex(
			"""(?i)(?:hi+|hello+|hey+|yo+|hiya|howdy|sup|what(?:'s| is) up|good morning|good afternoon|good evening)(?:\s+(?:there|bot|assistant))?[.!?,\s]*""",
		)
		private val PING_CONTEXT = Regex("""(?i)\b(?:ping|latency)\b""")
		private val PING_VALUE = Regex(
			"""(?i)\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(k)?\s*(?:ms|msec|milliseconds?)\b""",
		)
		private const val MAX_PING_MILLISECONDS = 1.0e15
		private const val SYSTEM_PROMPT =
			"You are a helpful general-purpose assistant. Help with questions and tasks " +
				"across topics, including explanations, writing, ideas, math, coding, and " +
				"conversation. Answer directly and clearly; be concise unless more detail " +
				"is requested. Do not invent facts or pretend to be certain: say when you " +
				"are unsure and ask for missing details only when needed. You can make " +
				"mistakes and may not know current events."
	}
}

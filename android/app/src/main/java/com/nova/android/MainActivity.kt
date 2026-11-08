package com.nova.android

import android.app.AlertDialog
import android.Manifest
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.os.Build
import android.text.InputType
import android.util.Base64
import android.view.Gravity
import android.view.inputmethod.EditorInfo
import android.widget.Button
import android.widget.EditText
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.lifecycle.lifecycleScope
import com.arm.aichat.AiChat
import com.arm.aichat.InferenceEngine
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.util.Locale

class MainActivity : AppCompatActivity() {
	private lateinit var statusText: TextView
	private lateinit var transcriptContent: LinearLayout
	private lateinit var transcriptScroll: ScrollView
	private lateinit var messageInput: EditText
	private lateinit var sendButton: Button
	private lateinit var setupButton: Button
	private lateinit var imageKeyButton: Button

	private var engine: InferenceEngine? = null
	private var modelReady = false
	private var busy = false
	private var imageApiKey: String? = null
	private var receiverRegistered = false

	private val notificationPermissionLauncher =
		registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
			if (granted) {
				startModelDownload()
			} else {
				AlertDialog.Builder(this)
					.setTitle("Allow download notifications?")
					.setMessage(
						"Nova uses a background service to keep the 533 MB download running. " +
							"Android hides its progress notification unless notifications are allowed. " +
							"Allow notifications to follow progress while Nova is in the background."
					)
					.setPositiveButton("Open settings") { _, _ ->
						startActivity(
							Intent(android.provider.Settings.ACTION_APP_NOTIFICATION_SETTINGS)
								.putExtra(android.provider.Settings.EXTRA_APP_PACKAGE, packageName),
						)
						setDownloadIdle()
					}
					.setNegativeButton("Continue anyway") { _, _ -> startModelDownload() }
					.setNeutralButton("Cancel") { _, _ -> setDownloadIdle() }
					.setOnCancelListener { setDownloadIdle() }
					.show()
			}
		}

	private val modelDownloadReceiver = object : BroadcastReceiver() {
		override fun onReceive(context: Context, intent: Intent) {
			val message = intent.getStringExtra(ModelDownloadService.EXTRA_MESSAGE)
				?: "Model download status updated."
			when (intent.action) {
				ModelDownloadService.ACTION_PROGRESS -> statusText.text = message
				ModelDownloadService.ACTION_COMPLETED -> {
					statusText.text = message
					busy = false
					loadLocalModel()
				}
				ModelDownloadService.ACTION_FAILED -> {
					statusText.text = message
					setDownloadIdle()
				}
			}
		}
	}

	override fun onCreate(savedInstanceState: Bundle?) {
		super.onCreate(savedInstanceState)
		buildChatScreen()
		setupButton.setOnClickListener { prepareLocalModel() }
		imageKeyButton.setOnClickListener { promptForImageApiKey() }
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

	override fun onStart() {
		super.onStart()
		val filter = IntentFilter().apply {
			addAction(ModelDownloadService.ACTION_PROGRESS)
			addAction(ModelDownloadService.ACTION_COMPLETED)
			addAction(ModelDownloadService.ACTION_FAILED)
		}
		ContextCompat.registerReceiver(
			this,
			modelDownloadReceiver,
			filter,
			ContextCompat.RECEIVER_NOT_EXPORTED,
		)
		receiverRegistered = true
		val modelFile = File(filesDir, "models/$MODEL_NAME")
		if (!modelReady && ModelDownloadService.downloadActive) {
			busy = true
			setupButton.isEnabled = false
			setupButton.text = "Downloading…"
			statusText.text = "Downloading the AI model in the background…"
			setupButton.postDelayed({
				val currentModelFile = File(filesDir, "models/$MODEL_NAME")
				if (setupButton.text == "Downloading…" &&
					!ModelDownloadService.downloadActive &&
					!modelReady
				) {
					if (currentModelFile.isFile && currentModelFile.length() == MODEL_SIZE) {
						busy = false
						loadLocalModel()
					} else {
						setDownloadIdle()
						statusText.text = "Download stopped. Tap Download text AI to try again."
					}
				}
			}, 1_000)
		} else if (!modelReady && modelFile.isFile && modelFile.length() == MODEL_SIZE) {
			prepareLocalModel()
		}
	}

	override fun onStop() {
		if (receiverRegistered) {
			unregisterReceiver(modelDownloadReceiver)
			receiverRegistered = false
		}
		super.onStop()
	}

	private fun buildChatScreen() {
		val background = Color.rgb(246, 247, 251)
		WindowCompat.setDecorFitsSystemWindows(window, false)
		WindowCompat.getInsetsController(window, window.decorView).apply {
			isAppearanceLightStatusBars = true
			isAppearanceLightNavigationBars = true
		}
		window.setSoftInputMode(android.view.WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE)

		val root = LinearLayout(this).apply {
			orientation = LinearLayout.VERTICAL
			setPadding(dp(18), dp(10), dp(18), dp(12))
			setBackgroundColor(background)
		}
		val brandMark = TextView(this).apply {
			text = "N"
			textSize = 23f
			setTextColor(Color.WHITE)
			gravity = Gravity.CENTER
			this.background = roundedBackground(Color.rgb(104, 83, 224), 18)
		}
		val titleBlock = LinearLayout(this).apply {
			orientation = LinearLayout.VERTICAL
			addView(TextView(this@MainActivity).apply {
				text = getString(R.string.app_name)
				textSize = 23f
				setTextColor(Color.rgb(30, 32, 48))
				setTypeface(typeface, android.graphics.Typeface.BOLD)
			})
			addView(TextView(this@MainActivity).apply {
				text = "Your creative AI companion"
				textSize = 13f
				setTextColor(Color.rgb(112, 115, 132))
			})
		}
		val header = LinearLayout(this).apply {
			orientation = LinearLayout.HORIZONTAL
			gravity = Gravity.CENTER_VERTICAL
			addView(brandMark, LinearLayout.LayoutParams(dp(46), dp(46)))
			addView(
				titleBlock,
				LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f).apply {
					marginStart = dp(12)
				},
			)
		}
		statusText = TextView(this).apply {
			text = "Ready when you are. Add an image key for pictures."
			textSize = 13f
			setTextColor(Color.rgb(75, 77, 95))
			setPadding(dp(12), dp(10), dp(12), dp(10))
			this.background = roundedBackground(Color.WHITE, 14, Color.rgb(230, 231, 238))
		}
		setupButton = Button(this).apply {
			text = "Download text AI"
			isAllCaps = false
			textSize = 13f
			setTextColor(Color.WHITE)
			this.background = roundedBackground(Color.rgb(104, 83, 224), 14)
			elevation = dp(2).toFloat()
		}
		imageKeyButton = Button(this).apply {
			text = "Image settings"
			isAllCaps = false
			textSize = 13f
			setTextColor(Color.rgb(81, 69, 173))
			this.background = roundedBackground(Color.rgb(235, 232, 255), 14)
		}
		transcriptScroll = ScrollView(this).apply {
			isFillViewport = true
			this.background = roundedBackground(Color.WHITE, 20, Color.rgb(232, 233, 240))
			clipToPadding = false
		}
		transcriptContent = LinearLayout(this).apply {
			orientation = LinearLayout.VERTICAL
			setPadding(dp(14), dp(18), dp(14), dp(18))
		}
		createTranscriptBubble(
			"Hi! I can help with questions, ideas, writing, coding, and creating pictures. What would you like to do?",
			isUser = false,
		)
		transcriptScroll.addView(
			transcriptContent,
			android.widget.FrameLayout.LayoutParams(
				android.view.ViewGroup.LayoutParams.MATCH_PARENT,
				android.view.ViewGroup.LayoutParams.WRAP_CONTENT,
			),
		)

		messageInput = EditText(this).apply {
			hint = "Message Nova..."
			inputType =
				InputType.TYPE_CLASS_TEXT or
					InputType.TYPE_TEXT_FLAG_MULTI_LINE or
					InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
			imeOptions = EditorInfo.IME_ACTION_SEND
			minLines = 1
			maxLines = 4
			textSize = 15f
			setTextColor(Color.rgb(34, 36, 52))
			setHintTextColor(Color.rgb(145, 147, 161))
			this.background = null
			setPadding(dp(12), dp(10), dp(8), dp(10))
		}
		sendButton = Button(this).apply {
			text = "↑"
			contentDescription = "Send message"
			textSize = 22f
			isAllCaps = false
			setTextColor(Color.WHITE)
			this.background = roundedBackground(Color.rgb(104, 83, 224), 16)
		}
		val composer = LinearLayout(this).apply {
			orientation = LinearLayout.HORIZONTAL
			gravity = Gravity.CENTER_VERTICAL
			this.background = roundedBackground(Color.WHITE, 20, Color.rgb(226, 227, 235))
			setPadding(dp(6), dp(4), dp(6), dp(4))
			elevation = dp(2).toFloat()
			addView(
				messageInput,
				LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f),
			)
			addView(
				sendButton,
				LinearLayout.LayoutParams(
					LinearLayout.LayoutParams.WRAP_CONTENT,
					LinearLayout.LayoutParams.WRAP_CONTENT,
				).apply { width = dp(48); height = dp(48) },
			)
		}

		root.addView(header)
		root.addView(statusText, LinearLayout.LayoutParams(
			LinearLayout.LayoutParams.MATCH_PARENT,
			LinearLayout.LayoutParams.WRAP_CONTENT,
		).apply { topMargin = dp(16) })
		val actions = LinearLayout(this).apply {
			orientation = LinearLayout.HORIZONTAL
			addView(
				setupButton,
				LinearLayout.LayoutParams(0, dp(48), 1f).apply { marginEnd = dp(6) },
			)
			addView(
				imageKeyButton,
				LinearLayout.LayoutParams(0, dp(48), 1f).apply { marginStart = dp(6) },
			)
		}
		root.addView(actions, LinearLayout.LayoutParams(
			LinearLayout.LayoutParams.MATCH_PARENT,
			LinearLayout.LayoutParams.WRAP_CONTENT,
		).apply { topMargin = dp(10) })
		root.addView(
			transcriptScroll,
			LinearLayout.LayoutParams(
				LinearLayout.LayoutParams.MATCH_PARENT,
				0,
				1f,
			).apply {
				topMargin = dp(12)
				bottomMargin = dp(12)
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

	private fun createTranscriptBubble(text: String, isUser: Boolean): TextView {
		val bubble = TextView(this).apply {
			this.text = text
			textSize = 15f
			setTextColor(if (isUser) Color.WHITE else Color.rgb(43, 45, 61))
			setPadding(dp(14), dp(11), dp(14), dp(11))
			setTextIsSelectable(true)
			this.background = roundedBackground(
				if (isUser) Color.rgb(104, 83, 224) else Color.rgb(245, 246, 250),
				18,
			)
		}
		val row = LinearLayout(this).apply {
			orientation = LinearLayout.HORIZONTAL
			gravity = if (isUser) Gravity.END else Gravity.START
			addView(
				bubble,
				LinearLayout.LayoutParams(
					LinearLayout.LayoutParams.WRAP_CONTENT,
					LinearLayout.LayoutParams.WRAP_CONTENT,
				).apply {
					if (isUser) marginStart = dp(42) else marginEnd = dp(42)
				},
			)
		}
		transcriptContent.addView(
			row,
			LinearLayout.LayoutParams(
				LinearLayout.LayoutParams.MATCH_PARENT,
				LinearLayout.LayoutParams.WRAP_CONTENT,
			).apply { bottomMargin = dp(10) },
		)
		return bubble
	}

	private fun appendTranscriptText(text: String, isUser: Boolean = false): TextView {
		val message = createTranscriptBubble(text, isUser)
		scrollToBottom()
		return message
	}

	private fun roundedBackground(
		color: Int,
		radiusDp: Int,
		strokeColor: Int? = null,
	): GradientDrawable =
		GradientDrawable().apply {
			setColor(color)
			cornerRadius = dp(radiusDp).toFloat()
			if (strokeColor != null) setStroke(dp(1), strokeColor)
		}

	private fun promptForImageApiKey() {
		val keyInput = EditText(this).apply {
			hint = "Google AI Studio API key"
			inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
			setText(imageApiKey.orEmpty())
			setSingleLine(true)
		}
		AlertDialog.Builder(this)
			.setTitle("Image generation key")
			.setMessage(
				"Nova sends image prompts to Google. The key stays in memory only and is not saved."
			)
			.setView(keyInput)
			.setPositiveButton("Save") { _, _ ->
				imageApiKey = keyInput.text.toString().trim().takeIf { it.isNotEmpty() }
				imageKeyButton.text = if (imageApiKey == null) "Set image key" else "Image key set"
				statusText.text =
					if (imageApiKey == null) "No image key set."
					else "Image key set for this app session."
			}
			.setNeutralButton("Clear") { _, _ ->
				imageApiKey = null
				imageKeyButton.text = "Set image key"
				statusText.text = "Image key cleared."
			}
			.setNegativeButton("Cancel", null)
			.show()
	}

	private fun prepareLocalModel() {
		if (busy || modelReady) return
		val modelFile = File(filesDir, "models/$MODEL_NAME")
		if (modelFile.isFile && modelFile.length() == MODEL_SIZE) {
			loadLocalModel()
			return
		}
		if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
			ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) !=
			PackageManager.PERMISSION_GRANTED
		) {
			setupButton.isEnabled = false
			statusText.text = "Allow notifications so Android can show the background download progress."
			notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
			return
		}
		startModelDownload()
	}

	private fun startModelDownload() {
		if (busy || modelReady) return
		busy = true
		setupButton.isEnabled = false
		setupButton.text = "Downloading…"
		statusText.text = "Starting the download. It can continue while Nova is in the background."
		try {
			ContextCompat.startForegroundService(
				this,
				Intent(this, ModelDownloadService::class.java)
					.setAction(ModelDownloadService.ACTION_DOWNLOAD),
			)
		} catch (error: IllegalStateException) {
			setDownloadIdle()
			statusText.text = "Android couldn't start the background download: ${error.message ?: "Please try again."}"
		} catch (error: SecurityException) {
			setDownloadIdle()
			statusText.text = "Android blocked the background download. Check Nova's notification permission."
		}
	}

	private fun loadLocalModel() {
		if (busy || modelReady) return
		busy = true
		setupButton.isEnabled = false
		setupButton.text = "Loading text AI…"
		statusText.text = "Checking and loading the downloaded AI. This can take a little while."
		lifecycleScope.launch {
			try {
				val modelFile = File(filesDir, "models/$MODEL_NAME")
				val verified = withContext(Dispatchers.IO) {
					modelFile.isFile &&
						modelFile.length() == MODEL_SIZE &&
						sha256(modelFile) == MODEL_SHA256
				}
				if (!verified) {
					if (modelFile.exists() && !modelFile.delete()) {
						throw IOException("The invalid model couldn't be removed. Free storage and try again.")
					}
					throw IOException("The downloaded model failed its integrity check. Tap Get text AI to download it again.")
				}
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
				setupButton.text = "Text AI ready"
				statusText.text = "Ready. Text runs locally; pictures use Google and need internet."
			} catch (error: CancellationException) {
				throw error
			} catch (error: Exception) {
				statusText.text = "Couldn't prepare the AI: ${error.message ?: error.javaClass.simpleName}"
				setupButton.isEnabled = true
				setupButton.text = "Try text AI again"
			} finally {
				busy = false
			}
		}
	}

	private fun setDownloadIdle() {
		busy = false
		setupButton.isEnabled = true
		setupButton.text = "Download text AI"
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
		if (question.isEmpty() || busy) return
		val wantsImage = IMAGE_GENERATION_REQUEST.containsMatchIn(question)
		if (!wantsImage && localEngine == null) {
			statusText.text = "Tap Download text AI for regular chat. Image prompts use the image key."
			return
		}
		val key = imageApiKey
		if (wantsImage && key.isNullOrBlank()) {
			statusText.text = "Tap Set image key before asking Nova to create a picture."
			return
		}

		busy = true
		messageInput.isEnabled = false
		sendButton.isEnabled = false
		messageInput.text.clear()
		appendTranscriptText("You: $question", isUser = true)
		val answerView = appendTranscriptText(
			if (wantsImage) "Nova: Creating your picture..." else "Nova: Thinking..."
		)
		scrollToBottom()
		statusText.text = if (wantsImage) "Creating picture online..." else "Thinking..."

		lifecycleScope.launch {
			try {
				if (wantsImage) {
					val generated = withContext(Dispatchers.IO) {
						generateImage(question, key.orEmpty())
					}
					val bitmap = withContext(Dispatchers.IO) {
						decodeGeneratedBitmap(generated.bytes)
					}
					answerView.text = "Nova: Here's your picture."
					val imageView = ImageView(this@MainActivity).apply {
						setImageBitmap(bitmap)
						scaleType = ImageView.ScaleType.FIT_CENTER
						adjustViewBounds = true
						maxHeight = dp(420)
						contentDescription = "Picture created by Nova"
					}
					transcriptContent.addView(
						imageView,
						LinearLayout.LayoutParams(
							LinearLayout.LayoutParams.MATCH_PARENT,
							LinearLayout.LayoutParams.WRAP_CONTENT,
						).apply { bottomMargin = dp(16) },
					)
					scrollToBottom()
				} else if (STANDALONE_GREETING.matches(question)) {
					answerView.text = "Nova: Hey! How can I help?"
				} else {
					val pingAnswer = answerPingTime(question)
					if (pingAnswer != null) {
						answerView.text = "Nova: $pingAnswer"
					} else {
						val answer = StringBuilder()
						val answerLength =
							if (DETAILED_REQUEST.containsMatchIn(question)) 384 else 192
						localEngine!!.sendUserPrompt(question, answerLength).collect { token ->
							answer.append(token)
							answerView.text = "Nova: $answer"
							scrollToBottom()
						}
						if (answer.isEmpty()) {
							answerView.text = "Nova: (No response generated.)"
						}
					}
				}
			} catch (error: CancellationException) {
				throw error
			} catch (error: Exception) {
				answerView.text = "Nova: [Request failed: ${error.message ?: error.javaClass.simpleName}]"
			} finally {
				busy = false
				messageInput.isEnabled = true
				sendButton.isEnabled = true
				statusText.text = if (modelReady) {
					"Ready. Text runs locally; image creation uses Google."
				} else {
					"Set an image key for pictures; download text AI for regular chat."
				}
				scrollToBottom()
			}
		}
	}

	private fun generateImage(prompt: String, apiKey: String): GeneratedImage {
		if (prompt.length > MAX_IMAGE_PROMPT_LENGTH) {
			throw IOException("Image prompts must be 4,000 characters or fewer.")
		}
		val connection = URL(IMAGE_API_URL).openConnection() as HttpURLConnection
		connection.connectTimeout = 30_000
		connection.readTimeout = 180_000
		connection.requestMethod = "POST"
		connection.doOutput = true
		connection.setRequestProperty("Content-Type", "application/json")
		connection.setRequestProperty("x-goog-api-key", apiKey)
		try {
			val requestBody = JSONObject()
				.put(
					"contents",
					org.json.JSONArray().put(
						JSONObject().put(
							"parts",
							org.json.JSONArray().put(JSONObject().put("text", prompt)),
						),
					),
				)
				.put(
					"generationConfig",
					JSONObject().put(
						"responseModalities",
						org.json.JSONArray().put("TEXT").put("IMAGE"),
					),
				)
			connection.outputStream.use { it.write(requestBody.toString().toByteArray(Charsets.UTF_8)) }
			val status = connection.responseCode
			val responseText = (if (status in 200..299) connection.inputStream else connection.errorStream)
				?.bufferedReader(Charsets.UTF_8)
				?.use { it.readText() }
				?: throw IOException("Google returned an empty image response (HTTP $status).")
			val response = try {
				JSONObject(responseText)
			} catch (error: Exception) {
				throw IOException("Google returned an invalid image response.", error)
			}
			if (status !in 200..299) {
				val errorMessage = response.optJSONObject("error")?.optString("message")
				throw IOException(
					errorMessage?.takeIf { it.isNotBlank() }
						?: "Google image generation failed (HTTP $status).",
				)
			}
			val candidates = response.optJSONArray("candidates")
				?: throw IOException("Google did not return an image.")
			for (candidateIndex in 0 until candidates.length()) {
				val parts = candidates.optJSONObject(candidateIndex)
					?.optJSONObject("content")
					?.optJSONArray("parts")
					?: continue
				for (partIndex in 0 until parts.length()) {
					val inlineData = parts.optJSONObject(partIndex)
						?.optJSONObject("inlineData")
						?: continue
					val mimeType = inlineData.optString("mimeType")
					if (mimeType !in SUPPORTED_IMAGE_TYPES) continue
					val encoded = inlineData.optString("data")
					if (encoded.isBlank()) continue
					val bytes = try {
						Base64.decode(encoded, Base64.DEFAULT)
					} catch (error: IllegalArgumentException) {
						throw IOException("Google returned invalid image data.", error)
					}
					if (bytes.isNotEmpty()) return GeneratedImage(mimeType, bytes)
				}
			}
			throw IOException("Google's response did not contain a generated image.")
		} finally {
			connection.disconnect()
		}
	}

	private fun decodeGeneratedBitmap(bytes: ByteArray): Bitmap {
		val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
		BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
		if (bounds.outWidth <= 0 || bounds.outHeight <= 0) {
			throw IOException("Nova received an image it couldn't display.")
		}
		val options = BitmapFactory.Options()
		var sampleSize = 1
		while (maxOf(bounds.outWidth, bounds.outHeight) / sampleSize > 1600) {
			sampleSize *= 2
		}
		options.inSampleSize = sampleSize
		return BitmapFactory.decodeByteArray(bytes, 0, bytes.size, options)
			?: throw IOException("Nova received an image it couldn't display.")
	}

	private fun scrollToBottom() {
		transcriptScroll.post { transcriptScroll.fullScroll(ScrollView.FOCUS_DOWN) }
	}

	private data class GeneratedImage(val mimeType: String, val bytes: ByteArray)

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
		private const val IMAGE_API_URL =
			"https://generativelanguage.googleapis.com/v1beta/models/" +
				"gemini-2.5-flash-image:generateContent"
		private const val MAX_IMAGE_PROMPT_LENGTH = 4000
		private val SUPPORTED_IMAGE_TYPES = setOf("image/png", "image/jpeg", "image/webp")
		private val IMAGE_GENERATION_REQUEST = Regex(
			"""(?is)\b(?:make|create|generate|draw|paint|design)\b.{0,80}\b(?:image|picture|photo|illustration|artwork|logo|wallpaper|portrait)\b|\b(?:image|picture|photo|illustration|artwork|logo|wallpaper|portrait)\s+of\b""",
		)
		private const val MODEL_NAME = "Qwen3.5-0.8B-Q4_K_M.gguf"
		private const val MODEL_SIZE = 532_517_120L
		private const val MODEL_SHA256 =
			"bd258782e35f7f458f8aced1adc053e6e92e89bc735ba3be89d38a06121dc517"
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

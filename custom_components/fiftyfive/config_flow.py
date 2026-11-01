"""Adds config flow for FiftyFive."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_COUNTRY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from slugify import slugify

from fiftyfive import CustomerType, Market

from .auth import (
    LoginResult,
    async_fetch_2fa_token,
    async_start_login,
    async_submit_2fa,
    build_base_url,
    extract_cookies,
)
from .const import (CONF_2FA_CODE, CONF_COOKIES, CONF_CUST_TYPE, DOMAIN, LOGGER,
                    CONF_LOCAL_SOURCES, CONF_POWER_ENTITY, CONF_ENERGY_ENTITY, CONF_MAX_POWER,
                    CONF_PRICE_MODE, CONF_FIXED_PRICE, CONF_PRICE_ENTITY)

if TYPE_CHECKING:
    from collections.abc import Mapping


class FiftyfiveFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for FiftyFive."""

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Configure optional external measurement sources without a new login."""
        return FiftyfiveOptionsFlow()


    def __init__(self) -> None:
        """Initialise the flow handler state."""
        # State that is carried across the (interactive) 2FA steps.
        self._login_input: dict[str, Any] = {}
        self._base_url: str = ""
        self._session = None
        self._2fa_token: str | None = None
        self._reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial (username/password) step."""
        _errors: dict[str, str] = {}
        if user_input is not None:
            # A fresh session (own cookie jar) is used for the whole login so
            # that the cookies we capture belong exclusively to this account.
            self._session = async_create_clientsession(self.hass)
            self._base_url = build_base_url(
                user_input[CONF_COUNTRY], user_input[CONF_CUST_TYPE]
            )
            self._login_input = user_input

            try:
                result = await async_start_login(
                    self._session,
                    self._base_url,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except Exception:  # noqa: BLE001 - surface any transport error as connection issue
                LOGGER.exception("Error while contacting the 50five portal")
                _errors["base"] = "connection"
            else:
                if result is LoginResult.TWO_FACTOR_REQUIRED:
                    LOGGER.debug("Credentials accepted, 2FA code required")
                    # Loading the /2fa page is what makes the portal actually
                    # e-mail the one time code to the user, so we must fetch it
                    # *before* prompting for the code (and reuse the CSRF token
                    # it contains when we submit the code later).
                    try:
                        self._2fa_token = await async_fetch_2fa_token(
                            self._session, self._base_url
                        )
                    except Exception:  # noqa: BLE001
                        LOGGER.exception(
                            "Error while requesting the 2FA code e-mail"
                        )
                        _errors["base"] = "connection"
                    else:
                        return await self.async_step_2fa()
                if result is LoginResult.OK:
                    # Portal did not ask for 2FA (backwards compatible path).
                    return await self._async_create_or_update_entry()
                LOGGER.warning("Invalid credentials/market.")
                _errors["base"] = "auth"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=(user_input or self._login_input or {}).get(
                            CONF_USERNAME, vol.UNDEFINED
                        ),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                    vol.Required(
                        CONF_PASSWORD,
                        # Pre-fill on re-authentication so the user can just
                        # confirm and move straight on to the fresh 2FA code.
                        default=(user_input or self._login_input or {}).get(
                            CONF_PASSWORD, vol.UNDEFINED
                        ),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        ),
                    ),
                    vol.Optional(
                        CONF_COUNTRY,
                        default=(user_input or self._login_input or {}).get(
                            CONF_COUNTRY, Market.NONE
                        ),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[m.value for m in Market], translation_key="country"
                        )
                    ),
                    vol.Required(
                        CONF_CUST_TYPE,
                        default=(user_input or self._login_input or {}).get(
                            CONF_CUST_TYPE, CustomerType.FORMER_SHELL
                        ),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[c.value for c in CustomerType],
                            translation_key="customer_type",
                        )
                    ),
                },
            ),
            errors=_errors,
            description_placeholders={
                "docs_url": "https://github.com/matzem79/home-assistant-fiftyfive"
            },
        )

    async def async_step_2fa(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the e-mailed two-factor code step."""
        _errors: dict[str, str] = {}
        if user_input is not None:
            try:
                accepted = await async_submit_2fa(
                    self._session,
                    self._base_url,
                    user_input[CONF_2FA_CODE],
                    token=self._2fa_token,
                )
            except Exception:  # noqa: BLE001
                LOGGER.exception("Error while submitting the 2FA code")
                _errors["base"] = "connection"
            else:
                if accepted:
                    LOGGER.debug("2FA code accepted")
                    return await self._async_create_or_update_entry()
                LOGGER.warning("Invalid 2FA code.")
                _errors["base"] = "invalid_2fa"

        return self.async_show_form(
            step_id="2fa",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_2FA_CODE): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                }
            ),
            errors=_errors,
            description_placeholders={
                "username": self._login_input.get(CONF_USERNAME, "")
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle re-authentication when the stored session expires."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        # Pre-fill the known values (from the existing entry) so the user only
        # has to confirm the password and supply a fresh 2FA code.
        self._login_input = dict(entry_data)
        return await self.async_step_user()

    async def async_step_reconfigure(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """
        Handle a user-initiated reconfiguration.

        This is the manual path the user takes when the session has expired.
        The integration never reconnects automatically and never requests a new
        2FA code on its own; a fresh 2FA e-mail is only sent when the user goes
        through this flow and submits their credentials.
        """
        entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        if entry is not None:
            self._reauth_entry = entry
            # Only seed the defaults on the first render, never overwrite the
            # values the user is actively editing in the form.
            if user_input is None:
                self._login_input = dict(entry.data)
        return await self.async_step_user(user_input)

    async def _async_create_or_update_entry(
        self,
    ) -> config_entries.ConfigFlowResult:
        """Persist the authenticated session and finish the flow."""
        cookies = extract_cookies(self._session)
        data = {
            **self._login_input,
            CONF_COOKIES: cookies,
        }
        # Do not persist any leftover 2FA code in the entry data.
        data.pop(CONF_2FA_CODE, None)

        unique_id = slugify(self._login_input[CONF_USERNAME])
        await self.async_set_unique_id(unique_id)

        if self._reauth_entry is not None:
            # Update the entry data (new session cookies). The update_listener
            # registered in async_setup_entry will automatically reload the entry,
            # so no explicit async_reload call is needed here.
            self.hass.config_entries.async_update_entry(
                self._reauth_entry, data=data
            )
            return self.async_abort(reason="reauth_successful")

        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=self._login_input[CONF_USERNAME],
            data=data,
        )


class FiftyfiveOptionsFlow(config_entries.OptionsFlow):
    """Assign optional energy and power entities to a single charger."""

    async def async_step_init(self, user_input=None):
        """Choose the charger whose sources should be edited."""
        if user_input is not None:
            self._charger = user_input["charger"]
            return await self.async_step_sources()
        networks = self.config_entry.runtime_data.coordinator.data
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Required("charger"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=[
                    {"value": str(n["IDX"]), "label": str(n.get("NAME") or n["IDX"])}
                    for n in networks
                ])
            )}),
        )

    async def async_step_sources(self, user_input=None):
        """Select local sensors and the maximum plausible power."""
        errors = {}
        sources = dict(self.config_entry.options.get(CONF_LOCAL_SOURCES, {}))
        current = sources.get(self._charger, {})
        if user_input is not None:
            for key, kind in ((CONF_POWER_ENTITY, "power"), (CONF_ENERGY_ENTITY, "energy")):
                entity_id = user_input.get(key)
                if entity_id and entity_id.startswith("sensor."):
                    state = self.hass.states.get(entity_id)
                    # Permit temporarily unavailable sensors, but validate units.
                    if state is None or state.attributes.get("unit_of_measurement") not in (
                        ("W", "kW") if kind == "power" else ("Wh", "kWh")
                    ):
                        errors[key] = "invalid_source"
            # Prevent feedback loops through this integration's own sensors.
            from homeassistant.helpers import entity_registry as er
            registry = er.async_get(self.hass)
            for key in (CONF_POWER_ENTITY, CONF_ENERGY_ENTITY):
                if registered := registry.async_get(user_input.get(key, "")):
                    if registered.platform == DOMAIN:
                        errors[key] = "invalid_source"
            mode = user_input.get(CONF_PRICE_MODE, "none")
            if mode == "entity":
                from .costs import price_value
                state = self.hass.states.get(user_input.get(CONF_PRICE_ENTITY, ""))
                if price_value(state, self.hass.config.currency) is None:
                    errors[CONF_PRICE_ENTITY] = "invalid_price"
                registered = registry.async_get(user_input.get(CONF_PRICE_ENTITY, ""))
                if registered is not None and registered.platform == DOMAIN:
                    errors[CONF_PRICE_ENTITY] = "invalid_price"
            if mode == "fixed" and CONF_FIXED_PRICE not in user_input:
                errors[CONF_FIXED_PRICE] = "invalid_price"
            if not errors:
                sources[self._charger] = user_input
                return self.async_create_entry(title="", data={
                    **self.config_entry.options, CONF_LOCAL_SOURCES: sources,
                })
        schema = {}
        for key, device_class in ((CONF_POWER_ENTITY, "power"), (CONF_ENERGY_ENTITY, "energy")):
            marker = vol.Optional(key, description={"suggested_value": current.get(key)})
            schema[marker] = selector.EntitySelector(selector.EntitySelectorConfig(
                domain="sensor",
            ))
        schema[vol.Required(CONF_MAX_POWER, default=current.get(CONF_MAX_POWER, 11.0))] = selector.NumberSelector(
            selector.NumberSelectorConfig(min=0.1, max=100, step=0.1, unit_of_measurement="kW", mode="box")
        )
        schema[vol.Required(CONF_PRICE_MODE, default=current.get(CONF_PRICE_MODE, "none"))] = selector.SelectSelector(
            selector.SelectSelectorConfig(options=["none", "fixed", "entity"], translation_key="price_mode")
        )
        schema[vol.Optional(CONF_FIXED_PRICE, description={"suggested_value": current.get(CONF_FIXED_PRICE)})] = selector.NumberSelector(
            selector.NumberSelectorConfig(min=-1000, max=1000, step="any", unit_of_measurement=f"{self.hass.config.currency}/kWh", mode="box")
        )
        schema[vol.Optional(CONF_PRICE_ENTITY, description={"suggested_value": current.get(CONF_PRICE_ENTITY)})] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        )
        return self.async_show_form(step_id="sources", data_schema=vol.Schema(schema), errors=errors)

"use client";

import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  searchRequestSchema,
  type SearchRequestInput,
  CONTACT_METHODS,
  CONTACT_METHOD_LABELS,
  FUEL_TYPES,
  FUEL_LABELS,
  GEARBOX_TYPES,
  GEARBOX_LABELS,
  VEHICLE_TYPES,
  VEHICLE_TYPE_LABELS,
  TIMELINE_OPTIONS,
  TIMELINE_LABELS,
} from "@/lib/validation";
import Reveal from "./Reveal";
import TurnstileWidget from "./TurnstileWidget";

const TURNSTILE_SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;

const inputClass =
  "w-full rounded-lg border border-black/10 bg-white px-4 py-3 text-sm text-ink placeholder:text-anthracite/40 focus:border-gold focus:outline-none focus:ring-2 focus:ring-gold/30 transition-colors";
const labelClass = "mb-1.5 block text-sm font-medium text-ink";
const errorClass = "mt-1.5 text-xs font-medium text-red-600";
const fieldsetTitleClass =
  "text-xs font-semibold uppercase tracking-[0.18em] text-gold-dark";

type Status = "idle" | "submitting" | "success" | "error";

export default function SearchForm() {
  const [status, setStatus] = useState<Status>("idle");
  const [serverError, setServerError] = useState<string | null>(null);
  const [turnstileToken, setTurnstileToken] = useState("");

  const {
    register,
    handleSubmit,
    control,
    formState: { errors },
    reset,
  } = useForm<SearchRequestInput>({
    resolver: zodResolver(searchRequestSchema),
    defaultValues: {
      preferredContactMethod: "telephone",
      website: "",
    },
  });

  const preferredContactMethod = useWatch({ control, name: "preferredContactMethod" });

  const onSubmit = async (data: SearchRequestInput) => {
    if (status === "submitting") return;
    setStatus("submitting");
    setServerError(null);

    try {
      const response = await fetch("/api/search-request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...data, turnstileToken }),
      });

      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { message?: string } | null;
        setServerError(body?.message ?? "Une erreur est survenue. Merci de réessayer.");
        setStatus("error");
        return;
      }

      setStatus("success");
      reset();
    } catch {
      setServerError("Une erreur réseau est survenue. Merci de réessayer.");
      setStatus("error");
    }
  };

  return (
    <section id="formulaire" className="bg-white py-24 sm:py-28">
      <div className="mx-auto max-w-content px-5 sm:px-8">
        <Reveal>
          <div className="mx-auto max-w-2xl text-center">
            <p className={fieldsetTitleClass}>Votre demande</p>
            <h2 className="mt-3 font-display text-3xl font-semibold text-ink sm:text-4xl">
              Quel véhicule recherchez-vous ?
            </h2>
            <p className="mt-4 text-sm leading-relaxed text-anthracite/70">
              Plus vous nous donnez de détails, plus notre recherche sera précise et rapide.
            </p>
          </div>
        </Reveal>

        <Reveal delay={100}>
          <div className="mx-auto mt-12 max-w-3xl rounded-xl2 border border-black/5 bg-cream/50 p-6 shadow-card sm:p-10">
            {status === "success" ? (
              <div className="py-10 text-center">
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={1.5}
                  className="mx-auto h-14 w-14 text-gold-dark"
                  aria-hidden
                >
                  <circle cx="12" cy="12" r="9.25" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="m8 12.5 2.5 2.5L16 9.5" />
                </svg>
                <h3 className="mt-6 font-display text-2xl font-semibold text-ink">
                  Votre demande a bien été envoyée !
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-anthracite/70">
                  L&apos;équipe MI LOC reviendra vers vous afin d&apos;échanger sur votre
                  recherche.
                </p>
                <button
                  type="button"
                  onClick={() => setStatus("idle")}
                  className="mt-8 text-sm font-semibold text-gold-dark underline underline-offset-4"
                >
                  Envoyer une autre demande
                </button>
              </div>
            ) : (
              <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-10">
                {/* Honeypot anti-spam — invisible pour un utilisateur humain */}
                <div className="absolute left-[-9999px] top-auto h-px w-px overflow-hidden" aria-hidden="true">
                  <label htmlFor="website">Ne pas remplir ce champ</label>
                  <input
                    id="website"
                    type="text"
                    tabIndex={-1}
                    autoComplete="off"
                    {...register("website")}
                  />
                </div>

                <fieldset>
                  <legend className={fieldsetTitleClass}>Coordonnées</legend>
                  <div className="mt-4 grid gap-5 sm:grid-cols-2">
                    <div>
                      <label className={labelClass} htmlFor="firstName">
                        Prénom <span className="text-gold-dark">*</span>
                      </label>
                      <input
                        id="firstName"
                        type="text"
                        autoComplete="given-name"
                        className={inputClass}
                        {...register("firstName")}
                      />
                      {errors.firstName && <p className={errorClass}>{errors.firstName.message}</p>}
                    </div>

                    <div>
                      <label className={labelClass} htmlFor="lastName">
                        Nom
                      </label>
                      <input
                        id="lastName"
                        type="text"
                        autoComplete="family-name"
                        className={inputClass}
                        {...register("lastName")}
                      />
                    </div>

                    <div>
                      <label className={labelClass} htmlFor="phone">
                        Téléphone
                      </label>
                      <input
                        id="phone"
                        type="tel"
                        autoComplete="tel"
                        className={inputClass}
                        placeholder="06 12 34 56 78"
                        {...register("phone")}
                      />
                      {errors.phone && <p className={errorClass}>{errors.phone.message}</p>}
                    </div>

                    <div>
                      <label className={labelClass} htmlFor="email">
                        Adresse e-mail
                      </label>
                      <input
                        id="email"
                        type="email"
                        autoComplete="email"
                        className={inputClass}
                        placeholder="vous@exemple.fr"
                        {...register("email")}
                      />
                      {errors.email && <p className={errorClass}>{errors.email.message}</p>}
                    </div>
                  </div>
                  <p className="mt-3 text-xs text-anthracite/55">
                    Merci de renseigner au moins un numéro de téléphone ou une adresse e-mail.
                  </p>
                </fieldset>

                <fieldset>
                  <legend className={fieldsetTitleClass}>Moyen de contact préféré</legend>
                  <div className="mt-4 flex flex-wrap gap-3">
                    {CONTACT_METHODS.map((method) => (
                      <label key={method} className="cursor-pointer">
                        <input
                          type="radio"
                          value={method}
                          className="peer sr-only"
                          {...register("preferredContactMethod")}
                        />
                        <span
                          className={`inline-flex rounded-full border px-4 py-2 text-sm font-medium transition-colors ${
                            preferredContactMethod === method
                              ? "border-ink bg-ink text-white"
                              : "border-black/15 bg-white text-anthracite/80 hover:border-ink/40"
                          }`}
                        >
                          {CONTACT_METHOD_LABELS[method]}
                        </span>
                      </label>
                    ))}
                  </div>
                </fieldset>

                <fieldset>
                  <legend className={fieldsetTitleClass}>Recherche véhicule</legend>
                  <div className="mt-4 grid gap-5 sm:grid-cols-2">
                    <div>
                      <label className={labelClass} htmlFor="brand">
                        Marque recherchée
                      </label>
                      <input id="brand" type="text" className={inputClass} {...register("brand")} />
                    </div>

                    <div>
                      <label className={labelClass} htmlFor="model">
                        Modèle recherché
                      </label>
                      <input id="model" type="text" className={inputClass} {...register("model")} />
                    </div>

                    <div>
                      <label className={labelClass} htmlFor="maxBudget">
                        Budget maximum (€) <span className="text-gold-dark">*</span>
                      </label>
                      <input
                        id="maxBudget"
                        type="number"
                        inputMode="numeric"
                        min={0}
                        className={inputClass}
                        {...register("maxBudget")}
                      />
                      {errors.maxBudget && <p className={errorClass}>{errors.maxBudget.message}</p>}
                    </div>

                    <div>
                      <label className={labelClass} htmlFor="minYear">
                        Année minimum souhaitée
                      </label>
                      <input
                        id="minYear"
                        type="number"
                        inputMode="numeric"
                        min={1980}
                        max={2100}
                        className={inputClass}
                        {...register("minYear")}
                      />
                      {errors.minYear && <p className={errorClass}>{errors.minYear.message}</p>}
                    </div>

                    <div>
                      <label className={labelClass} htmlFor="maxMileage">
                        Kilométrage maximum
                      </label>
                      <input
                        id="maxMileage"
                        type="number"
                        inputMode="numeric"
                        min={0}
                        className={inputClass}
                        {...register("maxMileage")}
                      />
                      {errors.maxMileage && <p className={errorClass}>{errors.maxMileage.message}</p>}
                    </div>

                    <div>
                      <label className={labelClass} htmlFor="fuelType">
                        Type de carburant
                      </label>
                      <select id="fuelType" className={inputClass} {...register("fuelType")}>
                        <option value="">—</option>
                        {FUEL_TYPES.map((fuel) => (
                          <option key={fuel} value={fuel}>
                            {FUEL_LABELS[fuel]}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className={labelClass} htmlFor="gearbox">
                        Boîte de vitesses
                      </label>
                      <select id="gearbox" className={inputClass} {...register("gearbox")}>
                        <option value="">—</option>
                        {GEARBOX_TYPES.map((gearbox) => (
                          <option key={gearbox} value={gearbox}>
                            {GEARBOX_LABELS[gearbox]}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className={labelClass} htmlFor="vehicleType">
                        Type de véhicule
                      </label>
                      <select id="vehicleType" className={inputClass} {...register("vehicleType")}>
                        <option value="">—</option>
                        {VEHICLE_TYPES.map((type) => (
                          <option key={type} value={type}>
                            {VEHICLE_TYPE_LABELS[type]}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                </fieldset>

                <fieldset>
                  <legend className={fieldsetTitleClass}>Précisez votre recherche</legend>
                  <div className="mt-4">
                    <textarea
                      id="details"
                      rows={5}
                      className={inputClass}
                      placeholder="Exemple : Renault Clio 5, finition Intens ou RS Line, moins de 80 000 km, caméra de recul, CarPlay, couleur noire ou grise…"
                      {...register("details")}
                    />
                  </div>

                  <div className="mt-5 grid gap-5 sm:grid-cols-2">
                    <div>
                      <label className={labelClass} htmlFor="color">
                        Couleur souhaitée
                      </label>
                      <input id="color" type="text" className={inputClass} {...register("color")} />
                    </div>

                    <div>
                      <label className={labelClass} htmlFor="mustHaveEquipment">
                        Équipements indispensables
                      </label>
                      <input
                        id="mustHaveEquipment"
                        type="text"
                        className={inputClass}
                        {...register("mustHaveEquipment")}
                      />
                    </div>

                    <div className="sm:col-span-2">
                      <label className={labelClass} htmlFor="timeline">
                        Délai d&apos;achat
                      </label>
                      <select id="timeline" className={inputClass} {...register("timeline")}>
                        <option value="">—</option>
                        {TIMELINE_OPTIONS.map((option) => (
                          <option key={option} value={option}>
                            {TIMELINE_LABELS[option]}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                </fieldset>

                {TURNSTILE_SITE_KEY && (
                  <TurnstileWidget siteKey={TURNSTILE_SITE_KEY} onToken={setTurnstileToken} />
                )}

                <fieldset>
                  <label className="flex items-start gap-3 text-sm text-anthracite/85">
                    <input
                      type="checkbox"
                      className="mt-0.5 h-4 w-4 shrink-0 rounded border-black/25 text-gold focus:ring-gold"
                      {...register("consent")}
                    />
                    <span>
                      J&apos;accepte que MI LOC utilise les informations renseignées afin de me
                      recontacter concernant ma recherche de véhicule.{" "}
                      <span className="text-gold-dark">*</span>
                    </span>
                  </label>
                  {errors.consent && <p className={errorClass}>{errors.consent.message}</p>}
                  <p className="mt-2 text-xs text-anthracite/55">
                    Vos informations sont uniquement utilisées pour traiter votre demande et vous
                    recontacter.
                  </p>
                </fieldset>

                {serverError && (
                  <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {serverError}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={status === "submitting"}
                  className="flex w-full items-center justify-center gap-2 rounded-full bg-ink px-8 py-4 text-base font-semibold text-white transition-all hover:bg-gold-dark disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
                >
                  {status === "submitting" && (
                    <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden>
                      <circle className="opacity-25" cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" />
                      <path className="opacity-90" d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
                    </svg>
                  )}
                  {status === "submitting" ? "Envoi en cours…" : "Envoyer ma recherche à MI LOC"}
                </button>
              </form>
            )}
          </div>
        </Reveal>
      </div>
    </section>
  );
}
